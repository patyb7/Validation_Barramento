# app/api/dependencies.py
from fastapi import Request, HTTPException, status
import logging
from typing import Dict, Any

from app.services.validation_service import ValidationService
from app.database.manager import DatabaseManager
from app.auth.api_key_manager import APIKeyManager

logger = logging.getLogger(__name__)

# Define a constante de mensagem de erro aqui
VALIDATION_SERVICE_NOT_READY_MESSAGE = "Serviço de validação não está pronto. Tente novamente mais tarde."


def get_validation_service(request: Request) -> ValidationService:
    """
    Dependência que fornece a instância do ValidationService.
    Assume que o ValidationService foi inicializado no lifespan da aplicação.
    """
    val_service: ValidationService = getattr(request.app.state, "validation_service", None)
    if not val_service:
        logger.critical("ValidationService não está disponível no estado da aplicação. Lifespan pode ter falhado.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=VALIDATION_SERVICE_NOT_READY_MESSAGE)
    return val_service

def get_db_manager(request: Request) -> DatabaseManager:
    """
    Dependência que fornece a instância do DatabaseManager.
    Assume que o DatabaseManager foi inicializado no lifespan da aplicação.
    """
    db_manager: DatabaseManager = getattr(request.app.state, "db_manager", None)
    if not db_manager:
        logger.critical("DatabaseManager não está disponível no estado da aplicação. Lifespan pode ter falhado.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gerenciador de banco de dados não está pronto.")
    return db_manager

def get_api_key_manager(request: Request) -> APIKeyManager:
    """
    Dependência que fornece a instância do APIKeyManager.
    Assume que o APIKeyManager foi inicializado no lifespan da aplicação.
    """
    api_key_manager: APIKeyManager = getattr(request.app.state, "api_key_manager", None)
    if not api_key_manager:
        logger.critical("APIKeyManager não está disponível no estado da aplicação. Lifespan pode ter falhado.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gerenciador de API Keys não está pronto.")
    return api_key_manager

def get_app_info(request: Request) -> Dict[str, Any]:
    """
    Dependência que fornece as informações da aplicação autenticada (app_info).
    Assume que o APIKeyAuthMiddleware já processou a API Key e armazenou app_info em request.state.
    """
    app_info: Dict[str, Any] = getattr(request.state, "app_info", None)
    if not app_info:
        logger.error("app_info não encontrado no request.state. O middleware de autenticação pode ter falhado ou a rota não é protegida por API Key.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autorizado: Informações da aplicação ausentes ou API Key inválida.")
    return app_info
def get_api_key(request: Request) -> str:
    """
    Dependência que extrai a API Key do cabeçalho da requisição.
    Assume que o cabeçalho 'x-api-key' é usado para autenticação.
    """
    api_key: str = request.headers.get("x-api-key")
    if not api_key:
        logger.error("API Key não encontrada no cabeçalho da requisição.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autorizado: API Key ausente.")
    return api_key