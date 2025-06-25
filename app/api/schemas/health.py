# app/api/schemas/health.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any

class HealthCheckResponse(BaseModel):
    """
    Schema de resposta para o endpoint de verificação de saúde da API.
    Fornece um resumo do status da aplicação e suas dependências.
    """
    status: str = Field(..., description="Status geral da aplicação (e.g., 'healthy', 'unhealthy').")
    message: str = Field(..., description="Mensagem descritiva do status da aplicação.")
    timestamp: datetime = Field(..., description="Timestamp da verificação de saúde.")
    dependencies: Dict[str, Any] = Field(..., description="Status de dependências individuais (e.g., banco de dados, carregamento de API keys).")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "message": "Serviço de Validação de Dados está operacional.",
                "timestamp": "2024-06-24T10:30:00Z",
                "dependencies": {
                    "database_connection": "healthy",
                    "api_key_loading": "healthy"
                }
            }
        }
