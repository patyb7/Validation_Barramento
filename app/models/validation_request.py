# app/models/validation_request.py
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class ValidationRequest(BaseModel):
    """
    Modelo Pydantic para a requisição de validação recebida pela API.
    """
    validation_type: str = Field(..., description="Tipo de validação a ser realizada (ex: 'telefone', 'cep', 'email', 'cpf_cnpj', 'endereco').")
    data: Dict[str, Any] = Field(..., description="Dados a serem validados. A estrutura varia conforme o `validation_type`.")
    client_identifier: Optional[str] = Field(None, description="Identificador único do cliente final que originou a requisição (ex: ID do usuário no sistema do cliente).")
    operator_id: Optional[str] = Field(None, description="ID do operador ou sistema que iniciou a validação, se aplicável.")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "validation_type": "telefone",
                    "data": {
                        "phone_number": "+5511987654321",
                        "country_hint": "BR"
                    },
                    "client_identifier": "CLIENTE_XPTO_001",
                    "operator_id": "API_GATEWAY"
                },
                {
                    "validation_type": "cpf_cnpj",
                    "data": {
                        "document_number": "123.456.789-00",
                        "cclub": "CLI-001-A" # Exemplo de dado para resolução da ClientEntity
                    },
                    "client_identifier": "CLIENTE_XPTO_001",
                    "operator_id": "API_GATEWAY"
                },
                {
                    "validation_type": "endereco",
                    "data": {
                        "logradouro": "Rua Augusta",
                        "numero": "1000",
                        "cidade": "São Paulo",
                        "estado": "SP",
                        "cep": "01305-000"
                    },
                    "client_identifier": "CLIENTE_XPTO_002"
                }
            ]
        }