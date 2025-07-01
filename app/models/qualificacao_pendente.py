import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, UUID4

class QualificacaoPendente(BaseModel):
    """
    Modelo Pydantic para a tabela 'qualificações_pendentes'.
    Representa um registro de validação que precisa de revalidação futura.
    """
    id: Optional[UUID4] = Field(default_factory=uuid.uuid4, description="ID único do registro de qualificação pendente.")
    validation_record_id: UUID4 = Field(description="ID do registro na tabela validation_records ao qual esta pendência se refere.")
    client_identifier: str = Field(max_length=255, description="Identificador do cliente para quem a validação está pendente.")
    validation_type: str = Field(max_length=100, description="Tipo de validação que está pendente (ex: 'telefone', 'pessoa_completa').")
    status_motivo: Optional[str] = Field(None, description="Detalhe do porquê o registro está pendente (ex: 'telefone incompleto').")
    attempt_count: int = Field(0, description="Contador de tentativas de revalidação.")
    last_attempt_at: Optional[datetime] = Field(None, description="Timestamp da última tentativa de revalidação.")
    scheduled_next_attempt_at: Optional[datetime] = Field(None, description="Timestamp da próxima tentativa agendada de revalidação.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp de criação do registro.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp da última atualização do registro.")

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u)
        }
class InvalidosQualificados(BaseModel):
    """
    Modelo Pydantic para a tabela 'invalidos_desqualificados'.
    Representa um registro de validação que foi definitivamente marcado como inválido
    após tentativas de qualificação ou por falha crítica.
    """
    id: Optional[UUID4] = Field(default_factory=uuid.uuid4, description="ID único do registro no arquivo de inválidos.")
    validation_record_id: UUID4 = Field(description="ID do registro na tabela validation_records ao qual este arquivo se refere.")
    client_identifier: Optional[str] = Field(None, max_length=255, description="Identificador do cliente associado ao registro inválido.")
    reason_for_invalidation: Optional[str] = Field(None, description="Motivo pelo qual o registro foi arquivado como inválido.")
    archived_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp de quando o registro foi arquivado como inválido.")

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u)
        }