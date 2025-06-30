# app/api/routers/validation.py
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, status, Query, Depends, Header, Body

# Importa os modelos Pydantic e a função de tratamento de erro do novo arquivo comum
from ..schemas.common import UniversalValidationRequest, ValidationResponse, handle_service_response_error

# Importa a função de dependência e a mensagem de erro do módulo de dependências
# ATENÇÃO: O caminho foi ajustado para ser absoluto a partir da raiz do projeto,
# o que é uma boa prática para evitar problemas de importação relativa em módulos complexos.
from app.api.dependencies import get_validation_service, VALIDATION_SERVICE_NOT_READY_MESSAGE

# Importa a classe ValidationService para tipagem, mas não a instância
from app.services.validation_service import ValidationService 

logger = logging.getLogger(__name__)

# O prefixo e as tags são definidos aqui para este roteador específico
router = APIRouter(prefix="/api/v1", tags=["Validation"])

# --- Endpoint de Validação ---
@router.post(
    "/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK, # O status HTTP inicial é 200, mas pode ser alterado por HTTPException
    summary="Valida dados de diversos tipos (telefone, endereço, etc.)",
    description="Recebe um tipo de validação (`phone`, `address`, `email`, `document`), os dados correspondentes, autentica a API Key e registra o resultado no banco de dados. Retorna o status da validação e detalhes."
)
async def validate_data_endpoint(
    # Injeta a instância do ValidationService. O FastAPI resolverá isso automaticamente
    # usando a função get_validation_service definida em app/api/dependencies.py.
    validation_service: ValidationService = Depends(get_validation_service),
    
    # Usa Body(...) para indicar que request_data é o corpo da requisição POST.
    request_data: UniversalValidationRequest = Body(...), 
    
    # Extrai o cabeçalho 'x-api-key' diretamente para uso.
    api_key_header: str = Header(..., alias="x-api-key") 
):
    """
    Realiza a validação de um dado específico através do ValidationService.
    """
    # Embora `Depends` geralmente garanta que o serviço esteja disponível,
    # uma verificação explícita aqui pode ser útil para depuração ou cenários muito específicos.
    if validation_service is None:
        logger.critical("ValidationService não inicializado no momento da requisição /api/v1/validate.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=VALIDATION_SERVICE_NOT_READY_MESSAGE
        )

    # Chama o método validate_data do serviço, passando a API Key e os dados da requisição.
    result = await validation_service.validate_data(
        api_key_str=api_key_header, 
        request=request_data
    )

    # Verifica se o serviço retornou um status de "error" (erro interno do serviço)
    if result.get("status") == "error":
        handle_service_response_error(result) # Usa a função auxiliar para levantar HTTPException

    # Se a validação interna do dado resultou em "is_valid: False",
    # queremos retornar um status HTTP 400 (Bad Request) para o cliente.
    # O `_build_response_payload` no ValidationService já define o campo 'code' para 200 ou 400.
    response_status_code = result.get("code", status.HTTP_200_OK if result.get("is_valid") else status.HTTP_400_BAD_REQUEST)
    
    logger.info(f"Retornando ValidationResponse com dados: {result}")
    
    # Se o resultado da validação for 'False', levanta uma HTTPException com o código 400
    # e a mensagem fornecida pelo serviço.
    if not result.get("is_valid"):
        raise HTTPException(
            status_code=response_status_code,
            detail=result.get("message"),
            headers={"X-Validation-Status": "Invalid"} # Cabeçalho customizado para indicar status
        )

    # Se tudo estiver OK e a validação for 'True', retorna o payload completo.
    return ValidationResponse(**result)