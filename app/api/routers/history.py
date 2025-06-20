# app/api/routers/history.py
"""
Validation_Barramento/app/api/routers/history.py
Este módulo define o endpoint de histórico de validação da API,
permitindo a consulta dos registros de validação.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Query, Depends, HTTPException, status

# Importa os modelos Pydantic e a função de tratamento de erro do common.py
from app.api.schemas.common import HistoryRecordResponse, HistoryResponse, handle_service_response_error
from app.api.dependencies import get_validation_service_instance, VALIDATION_SERVICE_NOT_READY_MESSAGE
from app.services.validation_service import ValidationService # Para type hinting

logger = logging.getLogger(__name__)

# CORREÇÃO: O prefixo "/api/v1" já é adicionado em main.py
router = APIRouter(tags=["History"])

# --- Endpoint de Histórico ---
@router.get("/history",
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtém o histórico de validações",
    description="Retorna uma lista dos últimos registros de validação, com opções de limite e inclusão de registros deletados."
)
async def get_history(
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a retornar."),
    include_deleted: bool = Query(False, description="Incluir registros logicamente deletados no histórico."),
    val_service: ValidationService = Depends(get_validation_service_instance)
):
    """
    Retorna os últimos N registros de validação do sistema,
    com a opção de incluir registros que foram logicamente deletados.
    """
    if val_service is None:
        logger.critical("ValidationService não inicializado no momento da requisição /history. (Erro de inicialização da dependência)")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=VALIDATION_SERVICE_NOT_READY_MESSAGE
        )
    
    # Chama o serviço de validação para obter o histórico
    records = await val_service.get_validation_history(
        limit=limit,
        include_deleted=include_deleted
    )

    # Converte os registros para o formato de resposta do Pydantic
    # O Pydantic ValidationRecord já foi corrigido para aceitar UUIDs e JSONB
    # então HistoryRecordResponse (que herda de ValidationRecord) deve funcionar.
    history_records_response = [HistoryRecordResponse.model_validate(record.model_dump()) for record in records]
    
    return HistoryResponse(
        status="success",
        message="Histórico obtido com sucesso.",
        data=history_records_response
    )

# --- Registro do Router ---
# Este router deve ser incluído no app principal em main.py.
# Exemplo de inclusão:
# app.include_router(history_router, prefix="/api/v1", tags=["History"])
