# app/api/routers/healt.py
# app/api/routers/health.py

import logging
from fastapi import APIRouter, Request, status, HTTPException
from app.api.schemas.health import HealthCheckResponse # CORRIGIDO: Importa do pacote schemas
from app.database.manager import DatabaseManager # Importa DatabaseManager
from app.auth.api_key_manager import APIKeyManager # Importa APIKeyManager
from app.database.repositories.log_repository import LogRepository, LogEntry # Importa LogRepository e LogEntry
from datetime import datetime, timezone # Importa datetime e timezone

logger = logging.getLogger(__name__)

# Instância do router para agrupar endpoints relacionados à saúde da aplicação
router = APIRouter()

# Constantes de mensagem
HEALTH_CHECK_FAILURE_MESSAGE = "Falha na verificação de saúde."
API_KEY_LOAD_FAILURE_MESSAGE = "Falha ao carregar API Keys."
DATABASE_CONNECTION_FAILURE_MESSAGE = "Falha na conexão com o banco de dados."

@router.get("/health", response_model=HealthCheckResponse, summary="Verificação de Saúde", tags=["Saúde"])
async def health_check(request: Request) -> HealthCheckResponse:
    """
    Verifica a saúde da aplicação, incluindo:
    - Status do banco de dados.
    - Status do carregamento das API Keys.
    """
    db_status = False
    api_keys_status = False
    overall_status = "unhealthy"
    message = "Serviço de Validação de Dados está offline."
    
    log_repo: LogRepository = getattr(request.app.state, 'log_repo', None)
    
    try:
        # Verifica o status do banco de dados
        db_manager: DatabaseManager = getattr(request.app.state, 'db_manager', None)
        if db_manager and db_manager.is_connected:
            # Tenta executar uma query simples para verificar a conexão ativa
            try:
                async with db_manager.get_connection() as conn:
                    await conn.execute("SELECT 1")
                db_status = True
                logger.debug("Health Check: Conexão com DB OK.")
            except Exception as e:
                db_status = False
                logger.error(f"Health Check: Falha na query de verificação do DB: {e}", exc_info=True)
                if log_repo:
                    await log_repo.add_log_entry(
                        LogEntry(
                            tipo_evento="HEALTH_CHECK_FALHA",
                            app_origem="HealthCheck",
                            usuario_operador="Sistema",
                            detalhes_evento_json={"component": "database", "error": str(e)},
                            status_operacao="FALHA",
                            mensagem_log=DATABASE_CONNECTION_FAILURE_MESSAGE
                        )
                    )
        else:
            logger.warning("Health Check: DatabaseManager não inicializado ou não conectado.")
            if log_repo:
                await log_repo.add_log_entry(
                    LogEntry(
                        tipo_evento="HEALTH_CHECK_FALHA",
                        app_origem="HealthCheck",
                        usuario_operador="Sistema",
                        detalhes_evento_json={"component": "database", "reason": "Manager not connected"},
                        status_operacao="FALHA",
                        mensagem_log=DATABASE_CONNECTION_FAILURE_MESSAGE
                    )
                )

        # Verifica o status do carregamento das API Keys
        api_key_manager: APIKeyManager = getattr(request.app.state, 'api_key_manager', None)
        if api_key_manager and api_key_manager._api_keys_data: # Acessa a propriedade interna para verificar se carregou dados
            api_keys_status = True
            logger.debug("Health Check: API Keys carregadas OK.")
        else:
            logger.warning("Health Check: APIKeyManager não inicializado ou chaves não carregadas.")
            if log_repo:
                await log_repo.add_log_entry(
                    LogEntry(
                        tipo_evento="HEALTH_CHECK_FALHA",
                        app_origem="HealthCheck",
                        usuario_operador="Sistema",
                        detalhes_evento_json={"component": "api_keys", "reason": "Keys not loaded"},
                        status_operacao="FALHA",
                        mensagem_log=API_KEY_LOAD_FAILURE_MESSAGE
                    )
                )

        if db_status and api_keys_status:
            overall_status = "healthy"
            message = "Serviço de Validação de Dados está operacional."
        elif not db_status:
            message = DATABASE_CONNECTION_FAILURE_MESSAGE
        elif not api_keys_status:
            message = API_KEY_LOAD_FAILURE_MESSAGE
        
        if overall_status == "unhealthy" and log_repo:
             await log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="HEALTH_CHECK_FALHA_GERAL",
                    app_origem="HealthCheck",
                    usuario_operador="Sistema",
                    detalhes_evento_json={"db_status": db_status, "api_keys_status": api_keys_status, "message": message},
                    status_operacao="FALHA",
                    mensagem_log=HEALTH_CHECK_FAILURE_MESSAGE
                )
            )

        return HealthCheckResponse(
            status=overall_status,
            message=message,
            timestamp=datetime.now(timezone.utc),
            dependencies={
                "database_connection": "healthy" if db_status else "unhealthy",
                "api_key_loading": "healthy" if api_keys_status else "unhealthy"
            }
        )
    except Exception as e:
        logger.critical(f"Erro fatal durante a verificação de saúde: {e}", exc_info=True)
        if log_repo:
            # Tenta logar o erro fatal no LogRepository
            # Se o log_repo em si estiver com problemas, esta parte pode falhar.
            try:
                await log_repo.add_log_entry(
                    LogEntry(
                        tipo_evento="HEALTH_CHECK_FALHA_FATAL",
                        app_origem="HealthCheck",
                        usuario_operador="Sistema",
                        detalhes_evento_json={"error": str(e)},
                        status_operacao="FALHA",
                        mensagem_log=f"Erro fatal no Health Check: {e}"
                    )
                )
            except Exception as log_exc:
                logger.error(f"Falha ao registrar log de erro fatal no LogRepository: {log_exc}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{HEALTH_CHECK_FAILURE_MESSAGE} Erro interno: {e}"
        )

