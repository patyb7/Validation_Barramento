# main.py

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any

# Importações organizadas
from app.config.settings import settings
from app.database.manager import DatabaseManager
from app.database.repositories.validation_record_repository import ValidationRecordRepository
from app.database.schema import initialize_database 
from app.auth.api_key_manager import APIKeyManager
from app.rules.decision_rules import DecisionRules
from app.services.validation_service import ValidationService

# Importação dos validadores existentes
from app.rules.phone.validator import PhoneValidator
from app.rules.address.cep.validator import CEPValidator 
from app.rules.email.validator import EmailValidator
from app.rules.document.cpf_cnpj.validator import CpfCnpjValidator
from app.rules.address.address_validator import AddressValidator

# Importação dos validadores de pessoa
from app.rules.pessoa.nome.validator import NomeValidator
from app.rules.pessoa.genero.validator import SexoValidator
from app.rules.pessoa.rg.validator import RGValidator 
from app.rules.pessoa.data_nascimento.validator import DataNascimentoValidator

# Importa o LogRepository e LogEntry
from app.database.repositories.log_repository import LogRepository
from app.models.log_entry import LogEntry

# --- IMPORTAR OS APIRouters DE CADA ARQUIVO DE ROTA ---
from app.api.routers.health import router as health_router
from app.api.routers.history import router as history_router
from app.api.routers.validation import router as validation_router

# --- Configuração de Logging Centralizada ---
logging.basicConfig(
    level=settings.get_log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# --- Gerenciador de Ciclo de Vida (Lifespan) Robusto ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    Inicializa recursos na partida e os libera de forma segura no desligamento.
    """
    logger.info("Fase de STARTUP do Lifespan iniciada... (main.py)")
    
    db_manager = DatabaseManager.get_instance() 
    
    try:
        await db_manager.connect(settings.DATABASE_URL) 

        await initialize_database(db_manager) 
        logger.info("Schema do banco de dados inicializado com sucesso.")

        validation_repo = ValidationRecordRepository(db_manager) 
        log_repo = LogRepository(db_manager) 
        
        api_key_manager = APIKeyManager(settings.API_KEYS_FILE) 
        
        decision_rules = DecisionRules(repo=validation_repo) 

        phone_validator = PhoneValidator()
        cep_validator = CEPValidator()
        email_validator = EmailValidator()
        cpf_cnpj_validator = CpfCnpjValidator()
        
        address_validator = AddressValidator(cep_validator=cep_validator)
        
        nome_validator = NomeValidator()
        sexo_validator = SexoValidator()
        rg_validator = RGValidator() 
        data_nascimento_validator = DataNascimentoValidator()
        
        validation_service = ValidationService(
            api_key_manager=api_key_manager,
            repo=validation_repo, 
            decision_rules=decision_rules,
            phone_validator=phone_validator,
            cep_validator=cep_validator,
            email_validator=email_validator,
            cpf_cnpj_validator=cpf_cnpj_validator,
            address_validator=address_validator,
            nome_validator=nome_validator,
            sexo_validator=sexo_validator,
            rg_validator=rg_validator, 
            data_nascimento_validator=data_nascimento_validator,
            log_repo=log_repo 
        )

        app.state.db_manager = db_manager
        app.state.validation_service = validation_service
        app.state.api_key_manager = api_key_manager
        app.state.log_repo = log_repo 

        logger.info("Fase de STARTUP do Lifespan concluída. Aplicação pronta para receber requisições.")
        
        yield 

    finally:
        logger.info("Fase de SHUTDOWN do Lifespan iniciada...")
        
        if getattr(app.state, 'db_manager', None) and app.state.db_manager.is_connected:
            await app.state.db_manager.close()
            logger.info("Pool de conexões com o banco de dados fechado.")
            
        logger.info("Fase de SHUTDOWN do Lifespan concluída.")

# --- Instância da Aplicação FastAPI ---
app = FastAPI(
    title="Barramento de Validação de Dados",
    version="1.0.0",
    description="Uma API robusta para validar e enriquecer dados diversos.",
    lifespan=lifespan
)

# --- Middleware de Autenticação API Key ---
class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.debug(f"Requisição recebida no middleware para o caminho: {request.url.path} (de {request.client.host}:{request.client.port})")
        
        if request.url.path.startswith(("/docs", "/openapi.json", "/redoc", "/api/v1/health")): 
            return await call_next(request)

        api_key = request.headers.get("x-api-key")
        if not api_key:
            logger.warning("API Key ausente no middleware para rota protegida.") 
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                content={"detail": "API Key ausente."}
            )
        
        api_key_manager: APIKeyManager = getattr(request.app.state, 'api_key_manager', None)
        if not api_key_manager:
            logger.critical("APIKeyManager não disponível no estado da aplicação durante o middleware. Configuração interna falhou.")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Configuração interna do servidor falhou. Contacte o suporte."}
            )

        app_info: Dict[str, Any] = api_key_manager.get_app_info(api_key)
        
        if not app_info or not app_info.get("is_active"):
            logger.warning(f"Tentativa de acesso com API Key inválida ou inativa: {api_key[:8]}...") 
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                content={"detail": "API Key inválida ou não autorizada."}
            )

        request.state.app_info = app_info
        request.state.auth_app_name = app_info.get("app_name") 
        request.state.can_delete_records = app_info.get("can_delete_records", False)
        request.state.can_check_duplicates = app_info.get("can_check_duplicates", False) 
        
        logger.info(f"API Key '{request.state.auth_app_name}' autenticada com sucesso para o caminho '{request.url.path}'.")

        if request.url.path.startswith("/api/v1/records/") and ("soft-delete" in request.url.path or "restore" in request.url.path):
             if not request.state.can_delete_records:
                logger.warning(f"Aplicação '{request.state.auth_app_name}' sem permissão para operação de delete/restore em {request.url.path}.")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Permissão negada para esta operação. Sua API Key não tem privilégios para deletar/restaurar registros."}
                )

        return await call_next(request)

app.add_middleware(APIKeyAuthMiddleware)

# --- Manipuladores de Exceção Globais ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception em '{request.url.path}': {exc.status_code} - {exc.detail}")
    
    log_repo = getattr(request.app.state, 'log_repo', None)
    app_name = getattr(request.state, 'auth_app_name', "Desconhecido")
    
    # Tentar extrair client_identifier do corpo da requisição se for uma requisição de validação
    client_entity_id_for_log = None
    if request.url.path == "/api/v1/validate" and request.method == "POST":
        try:
            # Não podemos await request.json() aqui, pois o corpo já pode ter sido lido.
            # A forma mais robusta seria pegar do request.state.request_data se fosse armazenado
            # consistentemente pelo middleware ou endpoint antes do erro.
            # Por simplicidade e para evitar re-leitura do corpo, vamos deixar como None aqui
            # para HttpExceptions que não vêm diretamente do service.
            pass
        except Exception:
            pass # Ignorar erro ao tentar ler corpo da requisição

    if log_repo:
        try:
            await log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="ERRO_HTTP",
                    app_origem=app_name,
                    usuario_operador=getattr(request.state, 'operator_id', "N/A"), # Tenta pegar operator_id do state
                    detalhes_evento_json={"path": request.url.path, "status_code": exc.status_code, "detail": exc.detail},
                    status_operacao="FALHA",
                    mensagem_log=f"Erro HTTP {exc.status_code}: {exc.detail}",
                    client_entity_id_afetado=client_entity_id_for_log # Passar o ID da entidade se disponível
                )
            )
        except Exception as log_exc:
            logger.error(f"Falha ao registrar log de erro HTTP: {log_exc}", exc_info=True)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    import traceback
    logger.critical(f"Erro inesperado (Exceção Geral) em '{request.url.path}': {exc}", exc_info=True)
    
    log_repo = getattr(request.app.state, 'log_repo', None)
    app_name = getattr(request.state, 'auth_app_name', "Desconhecido")
    
    client_entity_id_for_log = None
    # Tenta obter o client_entity_id do request.state se ele foi preenchido anteriormente
    # por um middleware ou endpoint antes do erro.
    if hasattr(request.state, 'request_data') and hasattr(request.state.request_data, 'client_identifier'):
        client_entity_id_for_log = request.state.request_data.client_identifier

    if log_repo:
        try:
            await log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="ERRO_INTERNO_FATAL",
                    app_origem=app_name,
                    usuario_operador=getattr(request.state, 'operator_id', "N/A"), # Tenta pegar operator_id do state
                    detalhes_evento_json={"path": request.url.path, "exception_type": type(exc).__name__, "exception_message": str(exc), "traceback": traceback.format_exc()},
                    status_operacao="FALHA",
                    mensagem_log=f"Erro interno fatal: {str(exc)}",
                    client_entity_id_afetado=client_entity_id_for_log # Passar o ID da entidade se disponível
                )
            )
        except Exception as log_exc:
            logger.error(f"Falha ao registrar log de erro fatal: {log_exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Ocorreu um erro interno inesperado. A equipe de desenvolvimento foi notificada."}
    )

# --- Rotas da API ---
@app.get("/", summary="Raiz da API", tags=["Status"])
async def root():
    """Endpoint raiz para verificar se a API está de pé."""
    return {"message": "Bem-vindo ao Barramento de Validação de Dados. Acesse /docs para a documentação da API."}

app.include_router(health_router, prefix="/api/v1") 
app.include_router(history_router, prefix="/api/v1") 
app.include_router(validation_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8001, 
        reload=True,
        log_level=settings.LOG_LEVEL.lower() 
    )
