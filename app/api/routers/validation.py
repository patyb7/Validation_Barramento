# app/api/routers/validation.py
"""
Validation_Barramento/app/api/routers/validation.py
Este módulo define o endpoint de validação de dados da API, permitindo a validação de diversos tipos de dados (telefone, endereço, email, documento) através do ValidationService.
"""
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, status, Query, Depends

# Importa os modelos Pydantic e a função de tratamento de erro do novo arquivo comum
from ..schemas.common import UniversalValidationRequest, ValidationResponse, handle_service_response_error
# Importa a função de dependência e a mensagem de erro de api_main
from app.api.dependencies import get_validation_service_instance, VALIDATION_SERVICE_NOT_READY_MESSAGE
from app.services.validation_service import ValidationService # Para type hinting

logger = logging.getLogger(__name__)

# CORREÇÃO: Removido o prefixo "/api/v1" daqui, pois ele já é adicionado em main.py
router = APIRouter(tags=["Validation"])

# --- Endpoint de Validação ---
@router.post("/validate", # Este caminho é relativo ao prefixo definido no include_router em main.py
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Valida dados de diversos tipos (telefone, endereço, etc.)",
    description="Recebe um tipo de validação (`phone`, `address`, `email`, `document`), os dados correspondentes, autentica a API Key e registra o resultado no banco de dados. Retorna o status da validação e detalhes."
)
async def validate_data_endpoint(
    request: Request,
    request_data: UniversalValidationRequest,
    val_service: ValidationService = Depends(get_validation_service_instance)
):
    """
    Realiza a validação de um dado específico através do ValidationService.
    """
    if val_service is None:
        logger.critical("ValidationService não inicializado no momento da requisição /validate. (Erro de inicialização da dependência)")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=VALIDATION_SERVICE_NOT_READY_MESSAGE
        )

    api_key_used = request.headers.get("x-api-key")

    result = await val_service.validate_data(
        api_key_str=api_key_used,
        request=request_data
    )

    if result.get("status") == "error":
        handle_service_response_error(result) 
    logger.info(f"Retornando ValidationResponse com dados: {result}")
    return ValidationResponse(**result)

# --- Registro do Router ---
# Este router deve ser incluído no app principal em main.py
# A inclusão deve ser feita no arquivo main.py, onde o app é criado.
# Exemplo de inclusão:
# app.include_router(router, prefix="/api/v1", tags=["Validation"])
# --- Fim do módulo validation.py ---
# Este módulo define o endpoint de validação de dados da API, permitindo a validação de diversos tipos de dados (telefone, endereço, email, documento) através do ValidationService.
# Ele também inclui o tratamento de erros e a autenticação de API Key.
# Certifique-se de que este router seja incluído no app principal em main.py
# para que as rotas sejam reconhecidas.
# --- Fim do módulo validation.py ---
# Certifique-se de que este router seja incluído no app principal em main.py
# para que as rotas sejam reconhecidas.
# --- Fim do módulo validation.py ---
# Certifique-se de que este router seja incluído no app principal em main.py
# para que as rotas sejam reconhecidas.