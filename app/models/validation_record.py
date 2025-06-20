# app/models/validation_record.py
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, UUID4 # Importe UUID4 para tipos UUID
import uuid

# Define o modelo para os detalhes de validação (pode ser genérico para todos os tipos)
class ValidationDetails(BaseModel):
    """
    Estrutura para armazenar detalhes específicos da validação.
    Pode conter chaves variadas dependendo do tipo de validação (e-mail, telefone, etc.).
    """
    # Usamos Field(default_factory=dict) para garantir que seja sempre um dicionário
    # se não for fornecido, evitando NoneType errors ao acessar subchaves.
    additional_info: Dict[str, Any] = Field(default_factory=dict)

    # Exemplo de campos que podem estar presentes para tipos específicos
    # is_disposable: Optional[bool] = None # Para e-mail
    # is_blacklisted: Optional[bool] = None # Para e-mail
    # domain_resolves: Optional[bool] = None # Para e-mail
    # phone_type: Optional[str] = None # Para telefone
    # country_code: Optional[int] = None # Para telefone
    # ddd_valid: Optional[bool] = None # Para telefone BR
    # is_sequential_or_repeated: Optional[bool] = None # Para telefone/documentos

    class Config:
        extra = "allow" # Permite campos extras que não estão explicitamente definidos aqui

# Define o modelo para o sumário de ações pós-validação (regras de decisão)
class PostValidationActionsSummary(BaseModel):
    """Sumário das ações de regras de decisão aplicadas após a validação."""
    soft_delete_action: Dict[str, Any] = Field(default_factory=dict)
    duplicate_check_action: Dict[str, Any] = Field(default_factory=dict)
    # Adicione outros conforme necessário
    class Config:
        extra = "allow" # Permite campos extras se as regras de negócio evoluírem

class BusinessRuleApplied(BaseModel):
    """Detalhes da regra de negócio específica aplicada."""
    code: str
    type: str
    message: Optional[str] = None
    # Parâmetros da regra de negócio podem ser um dicionário, mas podem ser nulos
    parameters: Optional[Dict[str, Any]] = None 

    class Config:
        extra = "allow" # Permite campos extras que não estão explicitamente definidos aqui


class ValidationRecord(BaseModel):
    """
    Modelo para representar um registro de validação no banco de dados.
    Corresponde à estrutura da tabela 'validation_records'.
    """
    # Usamos UUID4 para o tipo de ID. No Pydantic v2, UUID é o tipo nativo para UUIDs.
    # O Pydantic irá converter automaticamente a string UUID do DB para o objeto UUID.
    id: UUID4 = Field(default_factory=uuid.uuid4) # Gerado pelo DB, mas default para pydantic

    dado_original: str
    dado_normalizado: Optional[str] = None
    is_valido: bool
    mensagem: str
    origem_validacao: str
    tipo_validacao: str
    app_name: str
    client_identifier: Optional[str] = None

    # validation_details é um JSONB no DB, mapeamos para Dict[str, Any] ou para ValidationDetails model
    # Se for complexo, mantenha como Dict[str, Any] ou crie um modelo ValidationDetails mais específico.
    # Por agora, mantenho Dict[str, Any] para flexibilidade, mas garanto o default.
    validation_details: Dict[str, Any] = Field(default_factory=dict) 
    
    data_validacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # Popula automaticamente
    
    regra_negocio_codigo: Optional[str] = None
    regra_negocio_descricao: Optional[str] = None
    regra_negocio_tipo: Optional[str] = None
    # reg_neg_parametros é JSONB no DB, mapeamos para Dict[str, Any], pode ser None
    regra_negocio_parametros: Optional[Dict[str, Any]] = None 

    usuario_criacao: Optional[str] = None
    usuario_atualizacao: Optional[str] = None

    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    is_golden_record: Optional[bool] = False # Indica se este registro é um Golden Record
    golden_record_id: Optional[UUID4] = None # ID do Golden Record ao qual este registro pertence

    status_qualificacao: Optional[str] = None # Ex: 'QUALIFICADO', 'NAO_QUALIFICADO', 'PENDENTE'
    last_enrichment_attempt_at: Optional[datetime] = None # Última tentativa de enriquecimento

    client_entity_id: Optional[str] = None # ID da entidade do cliente (por exemplo, ID do usuário no sistema do cliente)

    class Config:
        from_attributes = True # Permite que o Pydantic crie instâncias a partir de atributos (ex: de um objeto de DB)
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u) # Garante que UUIDs sejam serializados como strings
        }
        populate_by_name = True # Para fields com alias

# Este é o modelo de resposta da API que o seu endpoint retorna
class ValidationResponse(BaseModel):
    """
    Modelo da resposta padronizada para as requisições de validação.
    """
    status: str # "success" ou "error"
    message: str # Mensagem de status ou erro
    is_valid: bool # Se o dado é válido
    # Os detalhes de validação podem ser um dicionário flexível
    validation_details: Dict[str, Any] 
    app_name: Optional[str] = None
    client_identifier: Optional[str] = None
    # record_id deve ser UUID4
    record_id: Optional[UUID4] = None 
    input_data_original: Optional[Union[str, Dict[str, Any]]] = None # Pode ser string ou JSON para endereço
    input_data_cleaned: Optional[Union[str, Dict[str, Any]]] = None # Pode ser string ou JSON para endereço
    tipo_validacao: Optional[str] = None
    origem_validacao: Optional[str] = None
    regra_negocio_codigo: Optional[str] = None
    regra_negocio_descricao: Optional[str] = None
    regra_negocio_tipo: Optional[str] = None
    regra_negocio_parametros: Optional[Dict[str, Any]] = None

    # Novos campos relacionados ao Golden Record e enriquecimento para a resposta
    is_golden_record_for_this_transaction: Optional[bool] = None
    golden_record_id_for_normalized_data: Optional[UUID4] = None 
    golden_record_data: Optional[Dict[str, Any]] = None # Dados do GR, se aplicável
    client_entity_id: Optional[str] = None
    status_qualificacao: Optional[str] = None
    last_enrichment_attempt_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u) # Garante que UUIDs sejam serializados como strings
        }
        populate_by_name = True
        extra = "allow" # Permite campos extras para maior flexibilidade na resposta
