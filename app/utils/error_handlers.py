import logging
from typing import Any, Dict
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

def handle_service_response_error(response: Dict[str, Any]):
    """
    Levanta uma HTTPException com base na resposta de erro de um serviço.
    Essa função encapsula a lógica comum de tratamento de erros da API.
    """
    detail_message = response.get("message", "Ocorreu um erro inesperado no serviço.")
    status_code = response.get("status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    logger.error(f"Erro do serviço: [Código: {status_code}] - {detail_message}. Detalhes: {response.get('data', 'N/A')}")
    raise HTTPException(status_code=status_code, detail=detail_message)