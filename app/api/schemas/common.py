# app/api/schemas/common.py
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, UUID4 # Importa UUID4 para tipos UUID

# Configuração de logging para este módulo
logger = logging.getLogger(__name__)

# Importa o modelo ValidationRecord para ser usado na resposta de histórico
# Assumimos que app.models.validation_record define o modelo ValidationRecord
try:
    from app.models.validation_record import ValidationRecord 
except ImportError:
    # Fallback ou tratamento de erro se ValidationRecord não puder ser importado
    # Este bloco é apenas para robustez em ambientes de teste/sem DB completo
    logger.warning("Não foi possível importar ValidationRecord de app.models.validation_record. As respostas de histórico podem estar incompletas ou o serviço pode se comportar de forma inesperada sem o DB.")
    
    # Define uma classe de fallback simplificada para ValidationRecord
    class ValidationRecord(BaseModel):
        id: UUID4 = Field(default_factory=uuid.uuid4, description="ID único do registro de validação.")
        dado_original: str = Field(..., description="Dado original submetido para validação.")
        dado_normalizado: Optional[str] = Field(None, description="Versão normalizada ou limpa do dado validado.")
        is_valido: bool = Field(..., description="Indica se o dado é considerado válido.")
        mensagem: str = Field(..., description="Mensagem descritiva sobre o resultado da validação.")
        origem_validacao: str = Field(..., description="Origem da validação (ex: 'servico_externo', 'base_interna').")
        tipo_validacao: str = Field(..., description="Tipo de validação realizada (ex: 'telefone', 'email').")
        app_name: str = Field(..., description="Nome da aplicação que executou a validação.")
        client_identifier: Optional[str] = Field(None, description="Identificador do cliente solicitante.")
        short_id_alias: Optional[str] = Field(None, description="Alias curto para o ID do registro.")
        validation_details: Dict[str, Any] = Field(default_factory=dict, description="Detalhes específicos da validação.")
        data_validacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp da validação.")
        regra_negocio_codigo: Optional[str] = Field(None, description="Código da regra de negócio aplicada.")
        regra_negocio_descricao: Optional[str] = Field(None, description="Descrição da regra de negócio aplicada.")
        regra_negocio_tipo: Optional[str] = Field(None, description="Tipo da regra de negócio (ex: 'fraude').")
        regra_negocio_parametros: Optional[Dict[str, Any]] = Field(None, description="Parâmetros da regra de negócio.")
        usuario_criacao: Optional[str] = Field(None, description="Usuário que criou o registro.")
        usuario_atualizacao: Optional[str] = Field(None, description="Usuário que atualizou o registro.")
        is_deleted: bool = Field(False, description="Indica se o registro foi logicamente deletado.")
        deleted_at: Optional[datetime] = Field(None, description="Timestamp da exclusão lógica.")
        created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp de criação do registro.")
        updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp da última atualização do registro.")
        is_golden_record: Optional[bool] = Field(False, description="Indica se este é um registro Golden Record.")
        golden_record_id: Optional[UUID4] = Field(None, description="ID do Golden Record associado, se existir.")
        status_qualificacao: Optional[str] = Field(None, description="Status de qualificação do dado.")
        last_enrichment_attempt_at: Optional[datetime] = Field(None, description="Timestamp da última tentativa de enriquecimento.")
        client_entity_id: Optional[str] = Field(None, description="ID da entidade cliente para correlação.")

        class Config:
            from_attributes = True
            json_encoders = {
                datetime: lambda dt: dt.isoformat(),
                uuid.UUID: lambda u: str(u) # Garante que UUIDs sejam string na saída JSON
            }
            populate_by_name = True # Updated from allow_population_by_field_name = True


# --- Modelos de Requisição ---
class UniversalValidationRequest(BaseModel):
    """
    Modelo genérico para as requisições de validação.
    `data` pode ser uma string (para telefone, email, cpf_cnpj)
    ou um dicionário (para endereço).
    """
    type: str = Field(..., description="O tipo de validação a ser realizada (ex: 'telefone', 'email', 'cpf_cnpj', 'endereco', 'cep').")
    data: Union[str, Dict[str, Any]] = Field(..., description="O dado a ser validado. Pode ser uma string (telefone, email, documento) ou um objeto (endereço).")
    client_identifier: Optional[str] = Field(None, description="Identificador único do cliente ou sistema que está a fazer a requisição.")
    operator_identifier: Optional[str] = Field(None, description="Identificador do operador ou usuário que iniciou a validação, se aplicável.")
    cclub: Optional[str] = Field(None, description="Código do CClub associado à transação.") 
    cpssoa: Optional[str] = Field(None, description="Código CPSSOA associado à transação.") 
    client_entity_id: Optional[str] = Field(None, description="ID da entidade cliente para correlação de registros, se aplicável. Será gerado se não fornecido.") 

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "telefone",
                    "data": "+5511987654321",
                    "client_identifier": "api_client_example",
                    "operator_identifier": "manual_test",
                    "client_entity_id": "user_123"
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
                    "client_entity_id": "org_abc_location_xyz"
                },
                {
                    "type": "email",
                    "data": "usuario@dominio.com.br",
                    "client_identifier": "api_client_example",
                    "operator_identifier": "batch_process",
                    "client_entity_id": "email_campaign_id_456"
                },
                {
                    "type": "cpf_cnpj",
                    "data": "12345678901",
                    "client_identifier": "api_client_example",
                    "operator_identifier": "form_submission",
                    "client_entity_id": "customer_data_upload_789"
                },
            ]
        }


# --- Modelos de Resposta ---
class ValidationResponse(BaseModel):
    """
    Modelo da resposta padronizada para as requisições de validação.
    """
    status: str = Field(..., description="Status geral da operação (ex: 'success', 'invalid', 'error').")
    message: str = Field(..., description="Mensagem descritiva sobre o resultado da validação.")
    is_valid: bool = Field(..., description="Indica se o dado validado é considerado válido.")
    validation_details: Dict[str, Any] = Field({}, description="Detalhes específicos da validação realizada.")
    app_name: str = Field(..., description="Nome da aplicação que realizou ou solicitou a validação.")
    client_identifier: Optional[str] = Field(None, description="Identificador do cliente que solicitou a validação.")
    record_id: Optional[UUID4] = Field(None, description="ID único do registro de validação persistido.") 
    short_id_alias: Optional[str] = Field(None, description="Alias curto do ID do registro para fácil referência.") 
    input_data_original: Any = Field(..., description="O dado original submetido para validação.")
    input_data_cleaned: Optional[Any] = Field(None, description="A versão normalizada ou limpa do dado validado, se aplicável.")
    tipo_validacao: str = Field(..., description="O tipo de validação que foi realizada.")
    origem_validacao: str = Field(..., description="A origem do validador (ex: 'servico_externo', 'base_interna').")
    
    # Campos de regras de negócio
    regra_negocio_codigo: Optional[str] = Field(None, description="Código da regra de negócio aplicada.")
    regra_negocio_descricao: Optional[str] = Field(None, description="Descrição da regra de negócio aplicada.")
    regra_negocio_tipo: Optional[str] = Field(None, description="Tipo da regra de negócio (ex: 'fraude', 'compliance').")
    regra_negocio_parametros: Optional[Dict[str, Any]] = Field(None, description="Parâmetros da regra de negócio aplicada.")

    # Golden Record Fields
    is_golden_record_for_this_transaction: Optional[bool] = Field(None, description="Indica se este registro se tornou o Golden Record para o dado normalizado nesta transação.")
    golden_record_id_for_normalized_data: Optional[UUID4] = Field(None, description="O ID do registro considerado o Golden Record para o dado normalizado relacionado.") 
    golden_record_data: Optional[Dict[str, Any]] = Field(None, description="Um resumo dos dados do Golden Record associado, se aplicável.")
    
    client_entity_id: Optional[str] = Field(None, description="ID da entidade cliente para correlação de registros, se aplicável.") 
    status_qualificacao: Optional[str] = Field(None, description="Status de qualificação do dado após validações adicionais (ex: 'QUALIFIED', 'UNQUALIFIED').") 
    last_enrichment_attempt_at: Optional[datetime] = Field(None, description="Timestamp da última tentativa de enriquecimento para o dado.") 

    class Config:
        from_attributes = True 
        json_encoders = {
            datetime: lambda dt: dt.isoformat(), 
            uuid.UUID: lambda u: str(u) 
        }
        populate_by_name = True 
        extra = "allow" # Permite campos extras para maior flexibilidade na resposta


class HistoryRecordResponse(ValidationRecord):
    """
    Modelo para um único registro retornado na lista de histórico.
    Herda de ValidationRecord, mas pode ser ajustado para incluir
    apenas os campos relevantes para a visualização do histórico.
    """
    pass


class HistoryResponse(BaseModel):
    """
    Modelo da resposta padronizada para as requisições de histórico.
    """
    status: str = Field(..., description="Status geral da operação (ex: 'success', 'error').")
    message: str = Field(..., description="Mensagem de status ou erro.")
    data: List[HistoryRecordResponse] = Field(default_factory=list, description="Lista de registros de histórico.")

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

def handle_validation_error(validation_errors: List[Dict[str, Any]]):
    """
    Função auxiliar para tratar erros de validação.
    Levanta uma HTTPException com detalhes dos erros de validação.
    """
    if not validation_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Erro de validação genérico sem detalhes específicos."
        )

    error_messages = []
    for error in validation_errors:
        code = error.get("code", "unknown_error")
        message = error.get("message", "Erro desconhecido")
        parameters = error.get("parameters", {})
        
        # Formata a mensagem de erro
        formatted_message = f"Erro {code}: {message}. Parâmetros: {parameters}"
        error_messages.append(formatted_message)

    # Loga os erros de validação
    logger.error(f"Erros de validação encontrados: {error_messages}")

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=error_messages
    )
# --- Exceções Personalizadas ---
class ValidationServiceError(Exception):
    """
    Exceção personalizada para erros no serviço de validação.
    Pode ser usada para encapsular erros específicos do serviço.
    """
    def __init__(self, message: str, code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(message)
        self.code = code
        logger.error(f"ValidationServiceError: {message} (Código: {code})")

    def __str__(self):
        return f"ValidationServiceError: {self.message} (Código: {self.code})"