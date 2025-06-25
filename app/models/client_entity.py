import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, UUID4 # Importa UUID4 para tipos UUID
from datetime import datetime, timezone 
import logging 

logger = logging.getLogger(__name__)

class ClientEntity(BaseModel):
    """
    Representa uma entidade cliente/pessoa única (Golden Record da Pessoa),
    agregando os IDs dos Golden Records de seus dados.
    """
    id: UUID4 = Field(default_factory=uuid.uuid4, description="ID único da entidade cliente (UUID).")
    main_document_normalized: str = Field(..., description="CPF ou CNPJ principal normalizado desta entidade.")
    cclub: Optional[str] = Field(None, description="Identificador CCLUB associado a esta entidade (se aplicável para distinguir sub-entidades do mesmo documento).")
    relationship_type: Optional[str] = Field(None, description="Tipo de relacionamento (ex: 'TITULAR', 'FILHO', 'DEPENDENTE', 'EMPRESA').")
    
    # IDs dos Golden Records para os dados desta entidade
    # Estes campos armazenam o 'id' do ValidationRecord que é o GR para aquele tipo de dado
    # CORRIGIDO: Alterado o tipo para UUID4 para alinhar com ValidationRecord.id
    golden_record_cpf_cnpj_id: Optional[UUID4] = Field(None, description="ID do GR do CPF/CNPJ principal.")
    golden_record_address_id: Optional[UUID4] = Field(None, description="ID do GR do Endereço.")
    golden_record_phone_id: Optional[UUID4] = Field(None, description="ID do GR do Telefone.")
    golden_record_email_id: Optional[UUID4] = Field(None, description="ID do GR do Email.")
    golden_record_cep_id: Optional[UUID4] = Field(None, description="ID do GR do CEP.")
    
    # Metadados
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp de criação da entidade no DB.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp da última atualização da entidade no DB.")
    
    # Quais apps contribuíram para a criação/atualização desta entidade
    # Armazena o app_name e o timestamp da última contribuição
    contributing_apps: Dict[str, datetime] = Field(default_factory=dict, description="Registro dos apps que contribuíram para esta entidade.") 

    class Config:
        from_attributes = True # Permite criar o modelo a partir de atributos de objetos (ex: registros de DB)
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u) # Garante que UUIDs sejam string na saída JSON
        }
        populate_by_name = True # Updated from allow_population_by_field_name = True

    def update_golden_record_id(self, validation_type: str, record_id: uuid.UUID): # CORRIGIDO: record_id agora é uuid.UUID
        """
        Atualiza o ID do Golden Record para um tipo de validação específico nesta entidade.
        """
        field_map = {
            "cpf_cnpj": "golden_record_cpf_cnpj_id",
            "endereco": "golden_record_address_id",
            "telefone": "golden_record_phone_id",
            "email": "golden_record_email_id",
            "cep": "golden_record_cep_id",
        }
        
        field_name = field_map.get(validation_type)
        if field_name:
            # Garante que o UUID seja atribuído corretamente
            setattr(self, field_name, record_id) 
            self.updated_at = datetime.now(timezone.utc)
        else:
            logger.warning(f"Tipo de validação desconhecido '{validation_type}' para ClientEntity.update_golden_record_id. O ID do Golden Record não foi atualizado.")

