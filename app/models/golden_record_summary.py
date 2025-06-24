from typing import Optional
from pydantic import BaseModel, Field, UUID4 # Adicionado UUID4
from datetime import datetime
import uuid # Necessário para uuid.UUID

class GoldenRecordSummary(BaseModel):
    """
    Modelo Pydantic para um resumo do Golden Record, usado na resposta da API.
    """
    # CORRIGIDO: ID agora é UUID4 para consistência com ValidationRecord
    id: UUID4 = Field(..., description="ID único do Golden Record (UUID).")
    dado_original: str = Field(..., description="O dado original do Golden Record.")
    dado_normalizado: Optional[str] = Field(None, description="O dado normalizado do Golden Record.")
    is_valido: bool = Field(..., description="Indica se o Golden Record é válido.")
    app_name: str = Field(..., description="Nome da aplicação que originou o Golden Record.")
    data_validacao: datetime = Field(..., description="Timestamp da validação do Golden Record.")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u) # Garante que UUIDs sejam string na saída JSON
        }
        json_schema_extra = {
            "example": {
                "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef", # Exemplo de UUID
                "dado_original": "(11)99999-1234",
                "dado_normalizado": "5511999991234",
                "is_valido": True,
                "app_name": "CRM_Principal",
                "data_validacao": "2025-06-16T10:30:00.000000+00:00" # ISO format com fuso horário
            }
        }

    def __str__(self):
        """
        Retorna uma representação em string do Golden Record.
        """
        return f"GoldenRecordSummary(id={self.id}, dado_original={self.dado_original}, is_valido={self.is_valido}, app_name={self.app_name})"
    def __repr__(self):
        """
        Retorna uma representação detalhada do Golden Record para debugging.
        """
        return (f"GoldenRecordSummary(id={self.id}, dado_original={self.dado_original}, "
                f"dado_normalizado={self.dado_normalizado}, is_valido={self.is_valido}, "
                f"app_name={self.app_name}, data_validacao={self.data_validacao.isoformat()})")
    def to_dict(self):
        """
        Retorna uma representação do Golden Record como um dicionário.
        """
        return {
            "id": self.id,
            "dado_original": self.dado_original,
            "dado_normalizado": self.dado_normalizado,
            "is_valido": self.is_valido,
            "app_name": self.app_name,
            "data_validacao": self.data_validacao
        }
    def to_json(self):
        """
        Retorna uma representação do Golden Record como uma string JSON.
        """
        import json
        return json.dumps(self.to_dict(), default=str)