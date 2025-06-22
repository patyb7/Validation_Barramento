# app/models/validation_record.py
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, UUID4 
import uuid
import hashlib # Importar hashlib para geração de hash

# Modelo para os detalhes de validação (sem alteração significativa para este problema)
class ValidationDetails(BaseModel):
    additional_info: Dict[str, Any] = Field(default_factory=dict)
    class Config:
        extra = "allow"

# Modelo para o sumário de ações pós-validação (sem alteração significativa)
class PostValidationActionsSummary(BaseModel):
    soft_delete_action: Dict[str, Any] = Field(default_factory=dict)
    duplicate_check_action: Dict[str, Any] = Field(default_factory=dict)
    class Config:
        extra = "allow"

# Modelo para regra de negócio aplicada (sem alteração significativa)
class BusinessRuleApplied(BaseModel):
    code: str
    type: str
    message: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None 
    class Config:
        extra = "allow"


class ValidationRecord(BaseModel):
    """
    Modelo para representar um registro de validação no banco de dados.
    Corresponde à estrutura da tabela 'validation_records'.
    """
    id: UUID4 = Field(default_factory=uuid.uuid4) 

    dado_original: str
    dado_normalizado: Optional[str] = None
    is_valido: bool
    mensagem: str
    origem_validacao: str
    tipo_validacao: str
    app_name: str
    client_identifier: Optional[str] = None

    # NOVO CAMPO: short_id_alias para visualização mais amigável
    short_id_alias: Optional[str] = None

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

    # Método para gerar o alias curto
    def generate_short_id_alias(self, length: int = 8) -> str:
        """Gera um alias curto a partir do UUID do registro usando SHA256."""
        if not self.id:
            return ""
        # Converte o UUID para string e então para bytes para o hashing
        hash_object = hashlib.sha256(str(self.id).encode('utf-8'))
        # Retorna os primeiros 'length' caracteres do hash hexadecimal
        return hash_object.hexdigest()[:length]

    # Hook do Pydantic para preencher o alias automaticamente ao criar/validar
    def model_post_init(self, __context: Any) -> None:
        # Só gera se o ID já existe (ex: veio do DB) e o alias não foi definido
        if self.id and self.short_id_alias is None:
            self.short_id_alias = self.generate_short_id_alias()

