# app/api/routers/history.py
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, status, Query, Depends

# Importa os modelos Pydantic e a função de tratamento de erro do arquivo comum
from app.api.schemas.common import HistoryRecordResponse, HistoryResponse, handle_service_response_error

# IMPORTAR A FUNÇÃO DE DEPENDÊNCIA E A MENSAGEM DE ERRO
from app.api.dependencies import get_validation_service_instance, VALIDATION_SERVICE_NOT_READY_MESSAGE 
from app.services.validation_service import ValidationService # Para type hinting

logger = logging.getLogger(__name__)

# CORREÇÃO: Removido o prefixo "/api/v1" daqui, pois ele já é adicionado em main.py
router = APIRouter(tags=["History & Records Management"])

# --- Endpoint de Histórico ---
@router.get(
    "/history", # Este caminho é relativo ao prefixo definido no include_router em main.py
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtém o histórico das últimas validações",
    description="Retorna uma lista dos últimos N registros de validação. Por padrão, não inclui registros deletados logicamente. Use `include_deleted=true` para visualizá-los."
)
async def get_history_endpoint(
    request: Request,
    val_service: ValidationService = Depends(get_validation_service_instance),
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

    history_result = await val_service.get_validation_history(
        api_key=request.headers.get("x-api-key"),
        limit=limit,
        include_deleted=include_deleted
    )

    if history_result.get("status") == "error":
        handle_service_response_error(history_result) 

    return HistoryResponse(**history_result)

# --- Endpoint de Soft Delete ---
@router.put(
    "/records/{record_id}/soft-delete", # Este caminho é relativo ao prefixo definido em main.py
    status_code=status.HTTP_200_OK,
    summary="Deleta logicamente um registro de validação",
    description="Marca um registro de validação como 'deletado' sem removê-lo fisicamente do banco de dados. Requer autenticação por API Key (apenas para usuários MDM, via configuração de permissões na API Key)."
)
async def soft_delete_record_endpoint(
    request: Request,
    record_id: str, # Alterado para str, assumindo que UUIDs são strings
    val_service: ValidationService = Depends(get_validation_service_instance)
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

    result = await val_service.soft_delete_record(request.headers.get("x-api-key"), record_id)
    if result.get("status") in ["error", "failed"]:
        handle_service_response_error(result) 
    return {"message": result.get("message")}

# --- Endpoint de Restore ---
@router.put(
    "/records/{record_id}/restore", # Este caminho é relativo ao prefixo definido em main.py
    status_code=status.HTTP_200_OK,
    summary="Restaura um registro de validação deletado logicamente",
    description="Reverte a operação de soft delete para um registro, tornando-o ativo novamente. Requer autenticação por API Key (apenas para usuários MDM, via configuração de permissões na API Key)."
)
async def restore_record_endpoint(
    request: Request,
    record_id: str, # Alterado para str, assumindo que UUIDs são strings
    val_service: ValidationService = Depends(get_validation_service_instance)
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

    result = await val_service.restore_record(request.headers.get("x-api-key"), record_id)
    if result.get("status") in ["error", "failed"]:
        handle_service_response_error(result) 
    return {"message": result.get("message")}

# --- Registro do Router ---
# Este router deve ser incluído no app principal em main.py
# A inclusão deve ser feita no arquivo main.py, onde o app é criado.
# Exemplo de inclusão:
# app.include_router(router, prefix="/api/v1", tags=["History & Records Management"])
# --- Fim do módulo history.py ---
# Este módulo define os endpoints para gerenciamento de histórico e registros de validação.
# Ele inclui a obtenção do histórico de validações, soft delete e restauração de registros.
# Certifique-se de que este router seja incluído no app principal em main.py
# para que as rotas sejam reconhecidas.
# --- Fim do módulo history.py ---
# Certifique-se de que este router seja incluído no app principal em main.py
# para que as rotas sejam reconhecidas.