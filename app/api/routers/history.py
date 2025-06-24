# app/routers/history.py
# app/api/routers/history.py

import logging
from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from typing import List, Dict, Any
from app.api.schemas.common import HistoryRecordResponse # Importa o modelo de resposta para histórico
from app.api.dependencies import get_validation_service, get_api_key_info # Importa dependências
from app.services.validation_service import ValidationService
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get(
    "/history",
    response_model=Dict[str, Any], # Pode ser HistoryResponse ou um Dict[str, Any] conforme a necessidade
    summary="Obter Histórico de Validações",
    tags=["Histórico"]
)
async def get_validation_history_endpoint(
    request: Request, # Adicionado Request para acessar app.state
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a serem retornados."),
    include_deleted: bool = Query(False, description="Incluir registros logicamente deletados."),
    validation_service: ValidationService = Depends(get_validation_service)
) -> Dict[str, Any]:
    """
    Retorna o histórico de validações para a aplicação associada à API Key.
    Acesso restrito apenas a API Keys com permissão.
    """
    api_key_str = request.headers.get("x-api-key") # Obtém a API Key do header
    
    if not api_key_str:
        logger.warning("Tentativa de acesso ao histórico sem API Key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key ausente."
        )

    # A validação da API Key e obtenção do app_info já é feita no middleware.
    # O app_info está disponível em request.state.app_info
    app_info = request.state.app_info if hasattr(request.state, 'app_info') else None
    
    if not app_info or not app_info.get("is_active"):
        logger.warning(f"Acesso não autorizado ao histórico com API Key inválida ou inativa.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida ou não autorizada."
        )

    # Verifica se a aplicação tem permissão para ler histórico.
    # Assumimos que 'get_api_key_info' já retorna essa permissão.
    # Ou podemos adicionar um campo 'can_read_history' na api_keys.json
    if not app_info.get("can_read_history", True): # Assume True por padrão se não definido
        logger.warning(f"Aplicação '{app_info.get('app_name')}' sem permissão para acessar o histórico.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão negada: Sua API Key não tem privilégios para acessar o histórico."
        )

    try:
        # Chama o serviço para obter o histórico
        history_response = await validation_service.get_validation_history(api_key_str, limit, include_deleted)
        return history_response
    except HTTPException as e:
        raise e # Re-lança exceções HTTP específicas do serviço
    except Exception as e:
        logger.error(f"Erro inesperado ao obter histórico de validações: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocorreu um erro inesperado ao recuperar o histórico."
        )
