# app/models/validation_record.py
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, UUID4 
import uuid
import hashlib # Importar hashlib para geração de hash

# Estes modelos auxiliares são definidos, mas ValidationRecord usa Dict[str, Any] para flexibilidade
# Se desejar usar tipagem mais forte, ValidationRecord precisaria ser ajustado para:
# validation_details: ValidationDetails
# e regra_negocio_parametros: BusinessRuleApplied (se fosse um objeto aninhado)

class ValidationDetails(BaseModel):
    additional_info: Dict[str, Any] = Field(default_factory=dict, description="Informações adicionais de validação.")
    class Config:
        extra = "allow" # Permite campos extras para maior flexibilidade

class PostValidationActionsSummary(BaseModel):
    soft_delete_action: Dict[str, Any] = Field(default_factory=dict, description="Detalhes da ação de soft delete.")
    duplicate_check_action: Dict[str, Any] = Field(default_factory=dict, description="Detalhes da verificação de duplicidade.")
    class Config:
        extra = "allow"

class BusinessRuleApplied(BaseModel):
    code: str = Field(..., description="Código da regra de negócio.")
    type: str = Field(..., description="Tipo da regra de negócio (ex: 'fraude', 'compliance').")
    message: Optional[str] = Field(None, description="Mensagem associada à regra de negócio.")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Parâmetros usados pela regra de negócio.") 
    class Config:
        extra = "allow"


class ValidationRecord(BaseModel):
    """
    Modelo para representar um registro de validação no banco de dados.
    Corresponde à estrutura da tabela 'validation_records'.
    """
    id: UUID4 = Field(default_factory=uuid.uuid4, description="ID único do registro de validação (UUID).") 
    dado_original: str = Field(..., description="O dado original que foi submetido para validação.")
    # CORREÇÃO: Mudar para str com um valor padrão de string vazia para evitar NotNullViolationError
    dado_normalizado: str = Field("", description="A versão normalizada ou limpa do dado validado.")
    # CORREÇÃO: REMOVER alias="is_valid" daqui. is_valido é o nome da coluna no DB.
    is_valido: bool = Field(..., description="Indica se o dado é considerado válido após a validação.")
    mensagem: str = Field(..., description="Mensagem descritiva sobre o resultado da validação.")
    origem_validacao: str = Field(..., description="A origem ou fonte da validação (ex: 'servico_externo', 'base_interna').")
    tipo_validacao: str = Field(..., description="O tipo de validação realizada (ex: 'telefone', 'email', 'cpf_cnpj', 'endereco').")
    app_name: str = Field(..., description="O nome da aplicação que iniciou a validação.")
    client_identifier: Optional[str] = Field(None, description="Um identificador do cliente solicitante, se aplicável.")
    # NOVO CAMPO: short_id_alias para visualização mais amigável
    short_id_alias: Optional[str] = Field(None, description="Um alias curto e amigável para o ID do registro.")
    validation_details: Dict[str, Any] = Field(default_factory=dict, description="Um dicionário flexível para detalhes adicionais específicos da validação.") 
    data_validacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="O timestamp da validação.")
    regra_negocio_codigo: Optional[str] = Field(None, description="Código da regra de negócio aplicada.")
    regra_negocio_descricao: Optional[str] = Field(None, description="Descrição da regra de negócio aplicada.")
    regra_negocio_tipo: Optional[str] = Field(None, description="Tipo da regra de negócio (ex: 'fraude', 'compliance', 'data_quality').")
    regra_negocio_parametros: Optional[Dict[str, Any]] = Field(None, description="Parâmetros específicos usados pela regra de negócio, se houver.") 
    usuario_criacao: Optional[str] = Field(None, description="Nome ou ID do usuário que criou o registro.")
    usuario_atualizacao: Optional[str] = Field(None, description="Nome ou ID do usuário que atualizou o registro pela última vez.")
    is_deleted: bool = Field(False, description="Flag que indica se o registro foi logicamente deletado (soft delete).")
    deleted_at: Optional[datetime] = Field(None, description="Timestamp da exclusão lógica, se aplicável.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp de criação do registro no banco de dados.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp da última atualização do registro no banco de dados.")
    is_golden_record: Optional[bool] = Field(False, description="Indica se este registro é o Golden Record para o seu dado normalizado.") 
    golden_record_id: Optional[UUID4] = Field(None, description="O ID do Golden Record associado a este dado normalizado, se existir e não for este registro.") 
    status_qualificacao: Optional[str] = Field(None, description="Status de qualificação do dado (ex: 'QUALIFIED', 'UNQUALIFIED', 'PENDING').") 
    last_enrichment_attempt_at: Optional[datetime] = Field(None, description="Timestamp da última tentativa de enriquecimento para este dado.") 
    client_entity_id: Optional[str] = Field(None, description="ID da entidade cliente (pessoa) à qual este dado pertence, para correlação.") 
    class Config:
        from_attributes = True # Permite criar o modelo a partir de atributos de objetos (ex: registros de DB)
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u) # Garante que UUIDs sejam string na saída JSON
        }
        populate_by_name = True # Permite que campos sejam preenchidos por alias ou nome de campo
        # Adicione outros campos conforme necessário, alinhando com o SQL e os requisitos do seu sistema
    def generate_short_id_alias(self, length: int = 8) -> str:
        """Gera um alias curto a partir do UUID do registro usando SHA256."""
        if not self.id:
            return "" # Retorna string vazia se não houver ID para gerar hash
        
        # Converte o UUID para string e então para bytes para o hashing
        hash_object = hashlib.sha256(str(self.id).encode('utf-8'))
        # Retorna os primeiros 'length' caracteres do hash hexadecimal
        return hash_object.hexdigest()[:length]
    # Hook do Pydantic para preencher o alias automaticamente ao criar/validar
    def model_post_init(self, __context: Any) -> None:
        # Só gera se o ID já existe (ex: veio do DB ou foi gerado na criação) e o alias não foi definido
        if self.id and self.short_id_alias is None:
            self.short_id_alias = self.generate_short_id_alias()
    def __str__(self):
        """
        Retorna uma representação em string do registro de validação.
        """
        return f"ValidationRecord(id={self.id}, dado_original={self.dado_original}, is_valido={self.is_valido}, app_name={self.app_name})"
