# app/api/api_main.py

from fastapi import FastAPI, Depends, HTTPException, Header, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

import atexit

# IMPORTAÇÕES ADICIONAIS NECESSÁRIAS PARA INICIALIZAR O SERVICE
from app.auth.api_key_manager import APIKeyManager
from app.database.manager import DatabaseManager
from app.database.repositories import ValidationRecordRepository
from app.rules.decision_rules import DecisionRules
from app.config.settings import settings
from app.services.validation_service import ValidationService, shutdown_service

# --- Inicialização das Dependências do ValidationService ---
# Isso deve ser feito APENAS UMA VEZ quando a aplicação inicia
db_manager = DatabaseManager()
repo = ValidationRecordRepository(db_manager)
api_key_manager = APIKeyManager(settings.API_KEYS)  # Passa as chaves de API configuradas

# MUDANÇA AQUI: Inicializa as regras de decisão com o repositório
decision_rules = DecisionRules(repo)

val_service = ValidationService(api_key_manager, repo, decision_rules) # Passa as dependências
atexit.register(shutdown_service)

app = FastAPI(
    title="Serviço de Validação Universal",
    description="Serviço centralizado para validar diversos tipos de dados (telefone, endereço, CPF/CNPJ, e-mail) com controle de regras por código e autenticação por API Key. Inclui funcionalidade de soft delete.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Modelos Pydantic ---

class UniversalValidationRequest(BaseModel):
    validation_type: str 
    data: Dict[str, Any] 
    client_identifier: Optional[str] = None 

class ValidationResponse(BaseModel):
    status: str 
    message: str 
    is_valid: bool 
    validation_details: Dict 
    app_info: Dict 
    record_id: Optional[int] = None 

class HistoryRecordResponse(BaseModel):
    """
    Modelo para um único registro retornado no histórico, incluindo soft delete fields.
    """
    id: int
    dado_original: str
    dado_normalizado: Optional[str] 
    valido: bool
    mensagem: str
    origem_validacao: str
    tipo_validacao: Optional[str] 
    data_validacao: datetime
    app_name: Optional[str]
    client_identifier: Optional[str]
    regra_codigo: Optional[str]
    validation_details: Dict[str, Any]
    is_deleted: bool # Campo de soft delete
    deleted_at: Optional[datetime] # Campo de soft delete

class HistoryResponse(BaseModel):
    status: str
    data: List[HistoryRecordResponse]
    message: Optional[str] = None 


# --- Endpoints da API ---

@app.post(
    "/api/v1/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Valida dados de diversos tipos (telefone, endereço, etc.)",
    description="Recebe um tipo de validação (`phone`, `address`, `email`, `document`), os dados correspondentes, autentica a API Key e registra o resultado no banco de dados. Retorna o status da validação e detalhes."
)
async def validate_data_endpoint(
    request_data: UniversalValidationRequest,
    x_api_key: str = Header(..., description="API Key para autenticar a aplicação chamadora. Ex: 'API_KEY_SEGUROS'")
):
    result = val_service.validate_data(
        api_key=x_api_key,
        validation_type=request_data.validation_type,
        data=request_data.data,
        client_identifier=request_data.client_identifier
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=result.get("code", status.HTTP_500_INTERNAL_SERVER_ERROR), detail=result.get("message"))
    
    return ValidationResponse(**result)

@app.get(
    "/api/v1/history",
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtém o histórico das últimas validações",
    description="Retorna uma lista dos últimos N registros de validação, exigindo autenticação por API Key. Os registros incluem detalhes do tipo de validação realizada. Por padrão, não inclui registros deletados logicamente. Use `include_deleted=true` para visualizá-los."
)
async def get_history_endpoint(
    x_api_key: str = Header(..., description="API Key para autenticar a aplicação chamadora"),
    limit: int = 5, # Parâmetro de query para limitar o número de registros retornados (default: 5)
    include_deleted: bool = False # Novo parâmetro para incluir registros deletados
):
    history_result = val_service.get_validation_history(x_api_key, limit, include_deleted=include_deleted)
    
    if history_result.get("status") == "error":
        raise HTTPException(status_code=history_result.get("code", status.HTTP_500_INTERNAL_SERVER_ERROR), detail=history_result.get("message"))
    
    return HistoryResponse(**history_result)


@app.put(
    "/api/v1/records/{record_id}/soft-delete",
    status_code=status.HTTP_200_OK,
    summary="Deleta logicamente um registro de validação",
    description="Marca um registro de validação como 'deletado' sem removê-lo fisicamente do banco de dados. Requer autenticação por API Key."
)
async def soft_delete_record_endpoint(
    record_id: int,
    x_api_key: str = Header(..., description="API Key para autenticar a aplicação chamadora")
):
    result = val_service.soft_delete_record(x_api_key, record_id)
    if result.get("status") == "error" or result.get("status") == "failed":
        raise HTTPException(status_code=result.get("code", status.HTTP_500_INTERNAL_SERVER_ERROR), detail=result.get("message"))
    return {"message": result.get("message")}

@app.put(
    "/api/v1/records/{record_id}/restore",
    status_code=status.HTTP_200_OK,
    summary="Restaura um registro de validação deletado logicamente",
    description="Reverte a operação de soft delete para um registro, tornando-o ativo novamente. Requer autenticação por API Key."
)
async def restore_record_endpoint(
    record_id: int,
    x_api_key: str = Header(..., description="API Key para autenticar a aplicação chamadora")
):
    result = val_service.restore_record(x_api_key, record_id)
    if result.get("status") == "error" or result.get("status") == "failed":
        raise HTTPException(status_code=result.get("code", status.HTTP_500_INTERNAL_SERVER_ERROR), detail=result.get("message"))
    return {"message": result.get("message")}


@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Verifica a saúde da API",
    description="Retorna o status 'ok' se a API estiver funcionando corretamente e acessível."
)
async def health_check():
    return {"status": "ok", "message": "API is running and healthy"}