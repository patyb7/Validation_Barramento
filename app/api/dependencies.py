# app/api/dependencies.py
# app/api/dependencies.py

from fastapi import Request, HTTPException, status
from typing import Dict, Any
from app.services.validation_service import ValidationService
from app.auth.api_key_manager import APIKeyManager
# Constantes para mensagens de erro
API_KEY_INVALID_MESSAGE = "API Key inválida ou não autorizada."
SERVICE_UNAVAILABLE_MESSAGE = "Serviço de validação não disponível."
API_KEY_MANAGER_UNAVAILABLE_MESSAGE = "Gerenciador de API Key não inicializado."

async def get_validation_service(request: Request) -> ValidationService:
    """
    Dependência que fornece a instância do ValidationService.
    Ele é armazenado no estado da aplicação após a inicialização do lifespan.
    """
    service = getattr(request.app.state, 'validation_service', None)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=SERVICE_UNAVAILABLE_MESSAGE
        )
    return service

async def get_api_key_info(request: Request) -> Dict[str, Any]:
    """
    Dependência que extrai e valida a API Key do cabeçalho da requisição.
    Retorna as informações da aplicação associadas à chave.
    
    Esta dependência será usada para endpoints que precisam de autenticação
    e acesso direto às informações da API Key.
    """
    api_key = request.headers.get("x-api-key")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key ausente."
        )
    
    api_key_manager: APIKeyManager = getattr(request.app.state, 'api_key_manager', None)
    if not api_key_manager:
        # Isto não deveria acontecer se o lifespan inicializou corretamente
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=API_KEY_MANAGER_UNAVAILABLE_MESSAGE
        )
    
    app_info = api_key_manager.get_app_info(api_key)
    
    if not app_info or not app_info.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=API_KEY_INVALID_MESSAGE
        )
    
    return app_info
