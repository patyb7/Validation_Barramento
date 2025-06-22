# app/api/routers/history.py
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid # Importar uuid para tipo UUID

from fastapi import APIRouter, Request, HTTPException, status, Query, Depends

# Importa os modelos Pydantic e a função de tratamento de erro do arquivo comum
from app.api.schemas.common import HistoryRecordResponse, HistoryResponse, handle_service_response_error

# IMPORTAR A FUNÇÃO DE DEPENDÊNCIA E A MENSAGEM DE ERRO
from app.api.dependencies import get_validation_service, VALIDATION_SERVICE_NOT_READY_MESSAGE, get_app_info 
from app.services.validation_service import ValidationService # Para type hinting

logger = logging.getLogger(__name__)

router = APIRouter(tags=["History & Records Management"])

# --- Endpoint de Histórico ---
@router.get(
    "/history", 
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtém o histórico das últimas validações",
    description="Retorna uma lista dos últimos N registros de validação. Por padrão, não inclui registros deletados logicamente. Use `include_deleted=true` para visualizá-los."
)
async def get_history_endpoint(
    request: Request,
    val_service: ValidationService = Depends(get_validation_service),
    app_info: Dict[str, Any] = Depends(get_app_info), # Injeta as informações da aplicação
    limit: int = Query(5, ge=1, le=100, description="Número máximo de registros a serem retornados (1-100)."),
    include_deleted: bool = Query(False, description="Incluir registros logicamente deletados.")
):
    """
    Obtém o histórico de validações registradas no sistema.
    """
    if val_service is None: 
        logger.critical("ValidationService não inicializado no momento da requisição /history. (Erro de inicialização da dependência)")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=VALIDATION_SERVICE_NOT_READY_MESSAGE
        )

    # CORREÇÃO AQUI: Passar app_info em vez de api_key
    history_result = await val_service.get_validation_history(
        app_info=app_info,
        limit=limit,
        include_deleted=include_deleted
    )

    if history_result.get("status") == "error":
        handle_service_response_error(history_result) 

    return HistoryResponse(**history_result)

# --- Endpoint de Soft Delete ---
@router.put(
    "/records/{record_id}/soft-delete", 
    status_code=status.HTTP_200_OK,
    summary="Deleta logicamente um registro de validação",
    description="Marca um registro de validação como 'deletado' sem removê-lo fisicamente do banco de dados. Requer autenticação por API Key (apenas para usuários MDM, via configuração de permissões na API Key)."
)
async def soft_delete_record_endpoint(
    request: Request,
    record_id: uuid.UUID, # Usar uuid.UUID como tipo
    val_service: ValidationService = Depends(get_validation_service),
    app_info: Dict[str, Any] = Depends(get_app_info) # Injeta as informações da aplicação
):
    """
    Marca um registro de validação como logicamente deletado.
    """
    if val_service is None:
        logger.critical("ValidationService não inicializado no momento da requisição /records/{record_id}/soft-delete. (Erro de inicialização da dependência)")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=VALIDATION_SERVICE_NOT_READY_MESSAGE
        )

    # CORREÇÃO AQUI: Passar app_info em vez de api_key
    result = await val_service.soft_delete_record(app_info, record_id)
    if result.get("status") in ["error", "failed"]:
        handle_service_response_error(result) 
    return {"message": result.get("message")}

# --- Endpoint de Restore ---
@router.put(
    "/records/{record_id}/restore", 
    status_code=status.HTTP_200_OK,
    summary="Restaura um registro de validação deletado logicamente",
    description="Reverte a operação de soft delete para um registro, tornando-o ativo novamente. Requer autenticação por API Key (apenas para usuários MDM, via configuração de permissões na API Key)."
)
async def restore_record_endpoint(
    request: Request,
    record_id: uuid.UUID, # Usar uuid.UUID como tipo
    val_service: ValidationService = Depends(get_validation_service),
    app_info: Dict[str, Any] = Depends(get_app_info) # Injeta as informações da aplicação
):
    """
    Restaura um registro de validação que foi logicamente deletado.
    """
    if val_service is None:
        logger.critical("ValidationService não inicializado no momento da requisição /records/{record_id}/restore. (Erro de inicialização da dependência)")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=VALIDATION_SERVICE_NOT_READY_MESSAGE
        )

    # CORREÇÃO AQUI: Passar app_info em vez de api_key
    result = await val_service.restore_record(app_info, record_id)
    if result.get("status") in ["error", "failed"]:
        handle_service_response_error(result) 
    return {"message": result.get("message")}

# --- Endpoint de Detalhes do Registro ---
@router.get(
    "/records/{record_id}",
    response_model=HistoryRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtém os detalhes de um registro de validação",
    description="Retorna os detalhes de um registro específico de validação, incluindo informações sobre a validação e o usuário que a realizou."
)
async def get_record_details_endpoint(
    request: Request,
    record_id: uuid.UUID, # Usar uuid.UUID como tipo
    val_service: ValidationService = Depends(get_validation_service),
    app_info: Dict[str, Any] = Depends(get_app_info) # Injeta as informações da aplicação
):
    """
    Obtém os detalhes de um registro de validação específico.
    """
    if val_service is None:
        logger.critical("ValidationService não inicializado no momento da requisição /records/{record_id}. (Erro de inicialização da dependência)")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=VALIDATION_SERVICE_NOT_READY_MESSAGE
        )

    # CORREÇÃO AQUI: Passar app_info em vez de api_key
    record_details = await val_service.get_record_details(app_info, record_id)
    if record_details.get("status") == "error":
        handle_service_response_error(record_details)

    return HistoryRecordResponse(**record_details)