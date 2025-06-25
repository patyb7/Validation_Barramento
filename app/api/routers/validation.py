import logging
from typing import Dict, Any, List, Optional, Union # Adicionada Union
from fastapi import APIRouter, Request, Depends, HTTPException, status
from app.services.validation_service import ValidationService
from app.api.schemas.common import UniversalValidationRequest, ValidationResponse, HistoryRecordResponse
from app.models.validation_record import ValidationRecord
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependência para o ValidationService
async def get_validation_service(request: Request) -> ValidationService:
    """Retorna a instância do ValidationService do estado da aplicação."""
    return request.app.state.validation_service

# Dependência para as informações da API Key
async def get_api_key_info(request: Request) -> Dict[str, Any]:
    """Retorna as informações da API Key do estado da requisição."""
    return request.state.app_info

@router.post("/validate",
             response_model=List[ValidationResponse], # O modelo de resposta agora é uma lista de ValidationResponse
             status_code=status.HTTP_200_OK,
             summary="Validar e Persistir Dados Diversos (Lote ou Único)",
             tags=["Validação"])
async def validate_data_endpoint(
    # Aceita tanto um único objeto UniversalValidationRequest quanto uma lista deles
    request_data: Union[UniversalValidationRequest, List[UniversalValidationRequest]],
    api_key_info: Dict[str, Any] = Depends(get_api_key_info),
    validation_service: ValidationService = Depends(get_validation_service)
) -> List[ValidationResponse]: # O tipo de retorno da função agora é List[ValidationResponse]
    """
    Endpoint principal para validação de dados. Recebe um tipo de validação e um payload de dados.
    Suporta o envio de um único objeto ou uma lista de objetos para validação em lote.
    Autentica a API Key e direciona para o validador apropriado.
    Persiste o resultado da validação e aplica regras de negócio.
    """
    logger.info("Requisição POST /api/v1/validate recebida (pode ser lote ou único).")

    # Garante que request_data_list é sempre uma lista para processamento uniforme
    if not isinstance(request_data, list):
        request_data_list = [request_data]
    else:
        request_data_list = request_data

    results: List[ValidationResponse] = []
    
    for item_data in request_data_list:
        logger.info(f"Processando validação para tipo: {item_data.validation_type}")
        # O ValidationService.validate_data espera um único UniversalValidationRequest
        service_response = await validation_service.validate_data(api_key_info, item_data)

        # Para requisições em lote, é comum retornar todos os resultados,
        # indicando falhas individualmente, em vez de levantar HTTPException no primeiro erro.
        # No entanto, para manter o comportamento anterior de "falha total" em caso de erro HTTP
        # de um item, mantemos a lógica de levantar HTTPException.
        if service_response.get("status_code", 200) >= 400:
            raise HTTPException(
                status_code=service_response.get("status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
                detail=service_response.get("message", "Erro desconhecido durante a validação de um item.")
            )
        
        # Adiciona o dicionário de resposta do serviço à lista de resultados.
        # FastAPI se encarregará de converter para ValidationResponse.
        results.append(service_response)

    # Retorna a lista de resultados. FastAPI a converterá para List[ValidationResponse].
    return results


@router.get("/records",
             response_model=List[HistoryRecordResponse],
             summary="Obter Histórico de Validações",
             tags=["Histórico"])
async def get_records(
    api_key_info: Dict[str, Any] = Depends(get_api_key_info),
    validation_service: ValidationService = Depends(get_validation_service),
    limit: int = 10,
    include_deleted: bool = False
) -> List[HistoryRecordResponse]:
    """
    Retorna o histórico de validações para a aplicação associada à API Key.
    Suporta paginação e filtragem de registros deletados.
    """
    logger.info(f"Requisição GET /api/v1/records recebida para app: {api_key_info.get('app_name')}")
    
    service_response = await validation_service.get_validation_history(
        api_key_str=api_key_info.get('api_key_string'), # Passa a string da API Key, que o service vai usar internamente para lookup
        limit=limit,
        include_deleted=include_deleted
    )

    if service_response.get("status_code", 200) >= 400:
        raise HTTPException(
            status_code=service_response.get("status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail=service_response.get("message", "Erro desconhecido ao obter histórico.")
        )
    
    return service_response.get("history", [])


@router.patch("/records/{record_id}/soft-delete",
              summary="Soft Delete de um Registro de Validação",
              tags=["Ações do Registro"])
async def soft_delete_record(
    record_id: uuid.UUID,
    api_key_info: Dict[str, Any] = Depends(get_api_key_info),
    validation_service: ValidationService = Depends(get_validation_service)
) -> Dict[str, str]:
    """
    Marca um registro de validação como 'soft-deletado' (exclusão lógica).
    Requer permissão específica da API Key.
    """
    logger.info(f"Requisição PATCH /api/v1/records/{record_id}/soft-delete recebida.")
    
    # A validação de permissão 'can_delete_records' já ocorre no middleware APIKeyAuthMiddleware
    # Se a requisição chegou aqui, a permissão já foi verificada.
    service_response = await validation_service.soft_delete_record(
        api_key_str=api_key_info.get('api_key_string'), # Passa a string da API Key
        record_id=record_id
    )

    if service_response.get("status_code", 200) >= 400:
        raise HTTPException(
            status_code=service_response.get("status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail=service_response.get("message", "Erro desconhecido ao realizar soft delete.")
        )
    
    return {"message": service_response.get("message", f"Registro {record_id} soft-deletado com sucesso.")}


@router.patch("/records/{record_id}/restore",
              summary="Restaurar um Registro de Validação",
              tags=["Ações do Registro"])
async def restore_record(
    record_id: uuid.UUID,
    api_key_info: Dict[str, Any] = Depends(get_api_key_info),
    validation_service: ValidationService = Depends(get_validation_service)
) -> Dict[str, str]:
    """
    Restaura um registro de validação que foi previamente soft-deletado.
    Requer permissão específica da API Key.
    """
    logger.info(f"Requisição PATCH /api/v1/records/{record_id}/restore recebida.")

    # A validação de permissão 'can_delete_records' já ocorre no middleware APIKeyAuthMiddleware
    service_response = await validation_service.restore_record(
        api_key_str=api_key_info.get('api_key_string'), # Passa a string da API Key
        record_id=record_id
    )

    if service_response.get("status_code", 200) >= 400:
        raise HTTPException(
            status_code=service_response.get("status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail=service_response.get("message", "Erro desconhecido ao restaurar registro.")
        )
    
    return {"message": service_response.get("message", f"Registro {record_id} restaurado com sucesso.")}
