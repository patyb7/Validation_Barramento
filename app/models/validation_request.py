# app/models/validation_request.py
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class ValidationRequest(BaseModel):
    """
    Modelo Pydantic para a requisição de validação de dados.
    Define a estrutura dos dados esperados na entrada da API para validação.
    """
    tipo_dado: str = Field(..., description="Tipo de dado a ser validado (ex: 'telefone', 'cep', 'email').")
    data: Dict[str, Any] = Field(..., description="Dicionário contendo os dados específicos para a validação. A estrutura varia conforme o 'tipo_dado'.")
    client_identifier: Optional[str] = Field(None, description="Identificador único do cliente que está realizando a requisição. Pode ser um ID de usuário, nome de serviço, etc.")
    operator_id: Optional[str] = Field(None, description="ID do operador ou sistema que iniciou a validação, se aplicável.")

    class Config:
        json_schema_extra = {
            "example": {
                "validation_type": "telefone",
                "data": {
                    "phone_number": "+5511987654321",
                    "country_hint": "BR"
                },
                "client_identifier": "cliente_abc_servico_x",
                "operator_id": "api_user_123"
            }
        }