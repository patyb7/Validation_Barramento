# app/models/validation_request.py
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class ValidationRequest(BaseModel):
    """
    Modelo Pydantic para a requisição de validação recebida pela API.
    Ajustado para estar em conformidade com a proposta do sistema robusto,
    onde 'client_entity_id' é gerado internamente pelo barramento.
    """
    validation_type: str = Field(..., description="Tipo de validação a ser realizada (ex: 'telefone', 'cep', 'email', 'cpf_cnpj', 'endereco').")
    data: Dict[str, Any] = Field(..., description="Dados a serem validados. A estrutura varia conforme o `validation_type`. Pode incluir 'cclub' para identificação da ClientEntity.")
    
    client_identifier: str = Field(..., description="Identificador único da aplicação cliente que originou a requisição (ex: 'CRM_App', 'ERP_System').")
    operator_id: Optional[str] = Field(None, description="ID do operador ou sistema que iniciou a validação (usuário de negócio ou automação).")
    
    # REMOVIDO: client_entity_id. Este campo será gerado internamente pelo barramento.

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "validation_type": "telefone",
                    "data": {
                        "phone_number": "+5511987654321",
                        "country_hint": "BR"
                    },
                    "client_identifier": "APP_VENDAS_001",
                    "operator_id": "USER_BART"
                    # client_entity_id não é enviado aqui
                },
                {
                    "validation_type": "cpf_cnpj",
                    "data": {
                        "document_number": "123.456.789-00",
                        "cclub": "CLI-001-A" # Este 'cclub' será usado para gerar o client_entity_id
                    },
                    "client_identifier": "APP_CADASTRO_002",
                    "operator_id": "SYS_INTEGRACAO"
                    # client_entity_id não é enviado aqui
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
                    "client_identifier": "APP_LOGISTICA_003"
                    # client_entity_id não é enviado aqui
                }
            ]
        }
