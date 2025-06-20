# app/models/golden_record_summary.py

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class GoldenRecordSummary(BaseModel):
    """
    Modelo Pydantic para um resumo do Golden Record, usado na resposta da API.
    """
    id: int = Field(..., description="ID único do Golden Record.")
    dado_original: str = Field(..., description="O dado original do Golden Record.")
    dado_normalizado: Optional[str] = Field(None, description="O dado normalizado do Golden Record.")
    is_valido: bool = Field(..., description="Indica se o Golden Record é válido.")
    app_name: str = Field(..., description="Nome da aplicação que originou o Golden Record.")
    data_validacao: datetime = Field(..., description="Timestamp da validação do Golden Record.")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 456,
                "dado_original": "(11)99999-1234",
                "dado_normalizado": "5511999991234",
                "is_valido": True,
                "app_name": "CRM_Principal",
                "data_validacao": "2025-06-16T10:30:00.000000Z"
            }
        }