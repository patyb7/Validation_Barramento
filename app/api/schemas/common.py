import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# --- Modelos Pydantic para Requisições ---
class UniversalValidationRequest(BaseModel):
    """
    Schema para requisições de validação universal.
    Define o tipo de validação e os dados a serem validados.
    """
    validation_type: str
    data: Dict[str, Any]
    client_identifier: Optional[str] = None
    operator_id: Optional[str] = None

# --- Modelos Pydantic para Respostas ---
class ValidationResponse(BaseModel):
    """
    Schema para respostas de validação.
    Inclui o status da validação, mensagem e detalhes.
    """
    status: str # 'success' ou 'error' ou 'failed' (se a validação em si falhou, não um erro de sistema)
    message: str
    is_valid: bool # Indica se o dado foi considerado válido ou não
    validation_details: Dict[str, Any] # Detalhes específicos da validação (ex: regras aplicadas, erros específicos)
    app_name: str # Nome da aplicação que fez a requisição
    client_identifier: Optional[str] = None # Identificador do cliente, se fornecido
    record_id: Optional[int] = None # ID do registro salvo no histórico, se aplicável
    input_data_original: Optional[str] = None # Dado original recebido
    input_data_cleaned: Optional[str] = None # Dado após limpeza/normalização (se houver)
    regra_negocio_codigo: Optional[str] = None # Código da regra de negócio aplicada
    tipo_validacao: Optional[str] = None # Tipo de validação realizada (ex: 'phone', 'address')
    origem_validacao: Optional[str] = None # Onde a validação foi originada (ex: 'api', 'batch')
    regra_negocio_descricao: Optional[str] = None # Descrição da regra de negócio
    regra_negocio_tipo: Optional[str] = None # Tipo da regra de negócio (ex: 'blacklist', 'format')
    regra_negocio_parametros: Optional[Dict[str, Any]] = None # Parâmetros da regra de negócio
    # NOVO: Status do ciclo de vida/qualificação do dado
    status_qualificacao: Optional[str] = None # ex: 'QUALIFIED', 'UNQUALIFIED_PENDING_ENRICHMENT', 'PERMANENTLY_UNQUALIFIED'

class HistoryRecordResponse(BaseModel):
    """
    Schema para um único registro no histórico de validações.
    Representa como um registro de histórico é retornado ao cliente.
    """
    id: int
    dado_original: str
    dado_normalizado: Optional[str]
    is_valido: bool
    mensagem: str
    origem_validacao: str
    tipo_validacao: Optional[str]
    data_validacao: datetime
    app_name: Optional[str]
    client_identifier: Optional[str]
    regra_negocio_codigo: Optional[str]
    regra_negocio_descricao: Optional[str] = None
    regra_negocio_tipo: Optional[str] = None
    regra_negocio_parametros: Optional[Dict[str, Any]] = None
    validation_details: Dict[str, Any]
    is_deleted: bool # Indica se o registro foi logicamente deletado
    deleted_at: Optional[datetime] # Timestamp da deleção lógica
    created_at: Optional[datetime] # Timestamp de criação do registro
    updated_at: Optional[datetime] # Timestamp da última atualização do registro
    # NOVOS CAMPOS PARA RASTREAR O STATUS DE QUALIFICAÇÃO E ENRIQUECIMENTO
    status_qualificacao: Optional[str] = None # ex: 'QUALIFIED', 'UNQUALIFIED_PENDING_ENRICHMENT', 'PERMANENTLY_UNQUALIFIED'
    # Adicionado para rastrear a última tentativa de enriquecimento (para o serviço de expurgo)
    last_enrichment_attempt_at: Optional[datetime] = None 


class HistoryResponse(BaseModel):
    """
    Schema para a resposta da API de histórico de validações.
    Contém o status geral e a lista de registros de histórico.
    """
    status: str # 'success' ou 'error'
    data: List[HistoryRecordResponse] # Lista de registros de histórico
    message: Optional[str] = None # Mensagem adicional, se houver

# --- Função auxiliar para tratamento de erros ---
def handle_service_response_error(result: Dict[str, Any]):
    """
    Auxilia no levantamento de HTTPException com base no dicionário de resultado do serviço.
    Extrai o código HTTP e a mensagem para uniformizar as respostas de erro da API.
    """
    status_code_from_result = result.get("code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    message = result.get("message", "Um erro inesperado ocorreu.")

    # Valida se o código HTTP retornado é um inteiro válido dentro do range HTTP.
    if not isinstance(status_code_from_result, int) or not (100 <= status_code_from_result < 600):
        status_code_from_result = status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.error(f"Código HTTP inválido retornado pelo serviço: {result.get('code')}. Usando 500 para {message}.")

    raise HTTPException(status_code=status_code_from_result, detail=message)