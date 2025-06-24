# app/api/schemas/common.py
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, UUID4  # Importe UUID4 para tipos UUID

# Importe o modelo ValidationRecord para ser usado na resposta de histórico
# Assumimos que app.models.validation_record define o modelo ValidationRecord
try:
    from app.models.validation_record import ValidationRecord 
except ImportError:
    # Fallback ou tratamento de erro se ValidationRecord não puder ser importado
    # Este bloco é apenas para robustez em ambientes de teste/sem DB completo
    logger.warning("Não foi possível importar ValidationRecord de app.models.validation_record. As respostas de histórico podem estar incompletas.")
    class ValidationRecord(BaseModel):
        id: UUID4 = Field(default_factory=uuid.uuid4)
        dado_original: str
        dado_normalizado: Optional[str] = None
        is_valido: bool
        mensagem: str
        origem_validacao: str
        tipo_validacao: str
        app_name: str
        client_identifier: Optional[str] = None
        validation_details: Dict[str, Any] = Field(default_factory=dict)
        data_validacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
        regra_negocio_codigo: Optional[str] = None
        regra_negocio_descricao: Optional[str] = None
        regra_negocio_tipo: Optional[str] = None
        regra_negocio_parametros: Optional[Dict[str, Any]] = None
        usuario_criacao: Optional[str] = None
        usuario_atualizacao: Optional[str] = None
        is_deleted: bool = False
        deleted_at: Optional[datetime] = None
        created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
        updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
        is_golden_record: Optional[bool] = False
        golden_record_id: Optional[UUID4] = None
        status_qualificacao: Optional[str] = None
        last_enrichment_attempt_at: Optional[datetime] = None
        client_entity_id: Optional[str] = None
        class Config:
            from_attributes = True
            json_encoders = {
                datetime: lambda dt: dt.isoformat(),
                uuid.UUID: lambda u: str(u)
            }
            populate_by_name = True


logger = logging.getLogger(__name__)

# --- Modelos de Requisição ---
class UniversalValidationRequest(BaseModel):
    """
    Modelo genérico para as requisições de validação.
    `data` pode ser uma string (para telefone, email, cpf_cnpj)
    ou um dicionário (para endereço).
    """
    type: str  # Ex: "telefone", "cpf_cnpj", "email", "endereco"
    data: Union[str, Dict[str, Any]]  # O dado a ser validado
    client_identifier: Optional[str] = None  # Identificador do cliente/sistema
    operator_identifier: Optional[str] = None  # Identificador do operador/usuário

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "telefone",
                    "data": "+5511987654321",
                    "client_identifier": "api_client_example",
                    "operator_identifier": "manual_test",
                },
                {
                    "type": "endereco",
                    "data": {
                        "logradouro": "Avenida Paulista",
                        "numero": "1578",
                        "bairro": "Cerqueira César",
                        "cidade": "São Paulo",
                        "estado": "SP",
                        "cep": "01310-200",
                        "complemento": "Edifício Itau",
                    },
                    "client_identifier": "api_client_example",
                    "operator_identifier": "system_integration",
                },
                {
                    "type": "email",
                    "data": "usuario@dominio.com.br",
                    "client_identifier": "api_client_example",
                    "operator_identifier": "batch_process",
                },
                {
                    "type": "cpf_cnpj",
                    "data": "12345678901",
                    "client_identifier": "api_client_example",
                    "operator_identifier": "form_submission",
                },
            ]
        }


# --- Modelos de Resposta ---


class ValidationResponse(BaseModel):
    """
    Modelo da resposta padronizada para as requisições de validação.
    """
    status: str  # "success" ou "error"
    message: str  # Mensagem de status ou erro
    is_valid: bool  # Se o dado é válido
    validation_details: Dict[str, Any] = Field(default_factory=dict)  # Garante dicionário vazio por padrão
    app_name: Optional[str] = None
    client_identifier: Optional[str] = None
    record_id: Optional[UUID4] = None  # Tipo correto para UUID
    input_data_original: Optional[Union[str, Dict[str, Any]]] = None
    input_data_cleaned: Optional[Union[str, Dict[str, Any]]] = None
    tipo_validacao: Optional[str] = None
    origem_validacao: Optional[str] = None
    regra_negocio_codigo: Optional[str] = None
    regra_negocio_descricao: Optional[str] = None
    regra_negocio_tipo: Optional[str] = None
    regra_negocio_parametros: Optional[Dict[str, Any]] = None  # Pode ser None

    is_golden_record_for_this_transaction: Optional[bool] = None
    golden_record_id_for_normalized_data: Optional[UUID4] = None  # Tipo correto para UUID
    golden_record_data: Optional[Dict[str, Any]] = None
    client_entity_id: Optional[str] = None
    status_qualificacao: Optional[str] = None
    last_enrichment_attempt_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda dt: dt.isoformat(), uuid.UUID: lambda u: str(u)}
        populate_by_name = True
        extra = "allow"  # Permite campos extras para maior flexibilidade na resposta


class HistoryRecordResponse(ValidationRecord):
    """
    Modelo para um único registro retornado na lista de histórico.
    Herda de ValidationRecord, mas pode ser ajustado para incluir
    apenas os campos relevantes para a visualização do histórico.
    """
    # Não é necessário adicionar campos aqui se ValidationRecord já for suficiente.
    # Se precisar de um subconjunto ou campos calculados, adicione aqui.
    pass


class HistoryResponse(BaseModel):
    """
    Modelo da resposta padronizada para as requisições de histórico.
    """
    status: str  # "success" ou "error"
    message: str  # Mensagem de status ou erro
    data: List[HistoryRecordResponse] = Field(default_factory=list)  # Lista de registros de histórico

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda dt: dt.isoformat(), uuid.UUID: lambda u: str(u)}
        populate_by_name = True


# --- Funções de Tratamento de Erro Comuns ---
def handle_service_response_error(result: Dict[str, Any]):
    """
    Função auxiliar para tratar respostas de erro do ValidationService.
    Levanta uma HTTPException apropriada.
    """
    status_code = result.get("code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    message = result.get("message", "Ocorreu um erro desconhecido no serviço de validação.")
    
    # Loga o erro com detalhes para depuração
    logger.error(f"Erro no serviço de validação: Status {status_code}, Mensagem: {message}, Detalhes: {result.get('validation_details')}")

    raise HTTPException(
        status_code=status_code,
        detail=message
    )

# --- Fim do módulo common.py ---
# Este módulo define os modelos de requisição e resposta para a API de validação,
# além de funções auxiliares para tratamento de erros e formatação de dados.
# Certifique-se de que este módulo seja importado corretamente nos endpoints
# que utilizam esses modelos e funções.
# --- Fim do módulo common.py ---