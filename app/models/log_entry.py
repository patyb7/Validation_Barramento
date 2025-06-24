# app/models/log_entry.py

from pydantic import BaseModel, Field, UUID4
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid

class LogEntry(BaseModel):
    """
    Representa uma entrada de log de auditoria para persistência no banco de dados.
    Este modelo espelha a estrutura da tabela `audit_logs`.
    """
    id: UUID4 = Field(default_factory=uuid.uuid4, description="ID único da entrada de log.")
    timestamp_evento: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp do evento de log.")
    tipo_evento: str = Field(..., description="Tipo do evento (ex: 'VALIDACAO_DADO', 'ACESSO_API_KEY', 'ERRO_SISTEMA').")
    app_origem: str = Field(..., description="Nome da aplicação ou serviço que originou o log.")
    usuario_operador: Optional[str] = Field(None, description="Identificador do usuário ou sistema que realizou a ação.")
    detalhes_evento_json: Dict[str, Any] = Field(default_factory=dict, description="Detalhes estruturados do evento em formato JSON.")
    status_operacao: str = Field(..., description="Status da operação ('SUCESSO', 'FALHA', 'EM_ANDAMENTO').")
    mensagem_log: str = Field(..., description="Mensagem descritiva legível do log.")
    related_record_id: Optional[UUID4] = Field(None, description="ID de um registro relacionado (ex: ID de ValidationRecord).")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp de criação do registro de log.")
    client_entity_id_afetado: Optional[str] = Field(None, description="ID da entidade cliente afetada pela operação.")
    
    class Config:
        from_attributes = True # Permite que o modelo seja criado a partir de atributos de objetos arbitrários
        populate_by_name = True # Permite mapeamento de campos por nome e alias
        json_encoders = {
            datetime: lambda dt: dt.isoformat(), # Serializa datetime para ISO 8601
            uuid.UUID: lambda u: str(u) # Serializa UUID para string
        }

