# app/api/dependencies.py
import logging
from fastapi import HTTPException, status, Depends, Request # <--- Adicione Request aqui!
from typing import Optional
from fastapi import Header # Adicione Header aqui (se for usar a dependência api_key_auth)

# Importa o DatabaseManager
from app.database.manager import DatabaseManager
# Importa ValidationService para type hinting
from app.services.validation_service import ValidationService

logger = logging.getLogger(__name__)

# --- Definição para DatabaseManager (para health check) ---
_db_manager_instance: Optional[DatabaseManager] = None

async def get_db_manager() -> DatabaseManager:
    global _db_manager_instance
    if _db_manager_instance is None:
        logger.warning("DatabaseManager sendo inicializado via dependência. É recomendado que a inicialização principal ocorra no startup da aplicação.")
        try:
            _db_manager_instance = DatabaseManager.get_instance() # Tenta obter a instância singleton já inicializada
            await _db_manager_instance.connect() # Conecta se ainda não estiver conectado
            logger.info("DatabaseManager acessado via dependência e conectado.")
        except Exception as e:
            logger.critical(f"Falha ao obter/inicializar DatabaseManager na dependência: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro interno: Falha ao conectar ao banco de dados."
            )
    return _db_manager_instance
async def get_validation_service_instance(request: Request) -> ValidationService:
    """
    Dependência que fornece a instância do ValidationService.
    Assume que validation_service já foi inicializado no startup_event de api_main.py
    e armazenado em app.state.
    """
    # Acesse a instância diretamente do estado da aplicação FastAPI
    validation_service: ValidationService = request.app.state.validation_service

    if validation_service is None:
        logger.critical("ValidationService não inicializado. Erro de configuração da aplicação. Certifique-se de que o startup da aplicação em api_main.py foi concluído com sucesso.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="O serviço de validação não está pronto. Tente novamente mais tarde."
        )
    return validation_service

VALIDATION_SERVICE_NOT_READY_MESSAGE = "O serviço de validação não está pronto. Tente novamente mais tarde."

# --- Dependência para autenticação de API Key ---
# AJUSTAR ESTA FUNÇÃO TAMBÉM SE ELA FOR USADA EM ROTAS (o middleware já faz a autenticação global)
async def api_key_auth(
    x_api_key: str = Depends(Header(alias="x-api-key")), # Pega a chave do cabeçalho
    validation_service: ValidationService = Depends(get_validation_service_instance) # Pega a instância do serviço
) -> None:
    """
    Dependência que autentica a API Key.
    Se a chave não for válida, lança uma HTTPException.
    """
    if not x_api_key:
        logger.error("API Key não fornecida.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key ausente."
        )

    # Use o api_key_manager do validation_service para validar a chave
    app_info = validation_service.api_key_manager.get_app_info(x_api_key)
    if not app_info:
        logger.error(f"Tentativa de acesso com API Key inválida: {x_api_key[:5]}...") # Log parcial da chave
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida."
        )
    logger.info(f"API Key '{app_info.get('app_name')}' autenticada com sucesso.")
    return None