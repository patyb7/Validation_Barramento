from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union # Adicionado Union

class AddressInput(BaseModel):
    """Modelo Pydantic para os dados de entrada de um endereço."""
    cep: Optional[str] = Field(None, description="Código de Endereçamento Postal (CEP)")
    logradouro: Optional[str] = Field(None, description="Nome da rua, avenida, etc.")
    numero: Optional[str] = Field(None, description="Número do imóvel")
    complemento: Optional[str] = Field(None, description="Complemento do endereço (apartamento, sala, etc.)")
    bairro: Optional[str] = Field(None, description="Nome do bairro")
    localidade: Optional[str] = Field(None, description="Nome da cidade")
    uf: Optional[str] = Field(None, description="Estado (Unidade Federativa) - sigla de 2 caracteres")
    ibge: Optional[str] = Field(None, description="Código IBGE do município")
    gia: Optional[str] = Field(None, description="Código GIA da localidade")
    ddd: Optional[str] = Field(None, description="DDD da localidade")
    siafi: Optional[str] = Field(None, description="Código SIAFI da localidade")

class CEPValidationDetails(BaseModel):
    """Detalhes da validação de CEP."""
    input_original: Optional[str] = Field(None, description="O CEP original fornecido.")
    cleaned_data: Optional[str] = Field(None, description="O CEP normalizado/limpo.")
    message: str = Field(..., description="Mensagem descritiva do resultado da validação do CEP.")
    origem_validacao: str = Field(..., description="Origem da validação do CEP (ex: 'correios_api', 'base_interna').")
    validation_code: str = Field(..., description="Código específico do resultado da validação do CEP.")
    address_found: Optional[bool] = Field(None, description="Indica se um endereço completo foi encontrado para o CEP.")
    external_api_data: Optional[Dict[str, Any]] = Field(None, description="Dados brutos retornados pela API externa de CEP, se usada.")
    api_error: Optional[str] = Field(None, description="Mensagem de erro da API externa, se ocorreu um erro.")
    external_api_response_raw: Optional[Dict[str, Any]] = Field(None, description="Resposta bruta da API externa antes de qualquer processamento.")

class AddressValidationResult(BaseModel):
    """Modelo Pydantic para o resultado da validação de endereço."""
    is_valid: bool = Field(..., description="Se o endereço é considerado válido.")
    dado_normalizado: Optional[str] = Field(None, description="O endereço normalizado em uma string formatada (ex: 'Rua ABC, 123 - Bairro').")
    mensagem: str = Field(..., description="Mensagem explicativa do resultado geral da validação do endereço.")
    origem_validacao: str = Field("address_validator", description="Fonte principal da validação do endereço.")
    
    # CORREÇÃO/SUGESTÃO APLICADA: Tipagem mais específica para 'details'
    # Permite que 'cep_validation' seja um CEPValidationDetails e outras chaves sejam Any
    details: Dict[str, Union[CEPValidationDetails, Any]] = Field(..., description="Detalhes adicionais da validação, podendo incluir 'cep_validation'.")
    
    business_rule_applied: Dict[str, Any] = Field(..., description="Detalhes da regra de negócio aplicada que levou ao resultado final.")

    class Config:
        from_attributes = True # Permite criar o modelo a partir de atributos de objetos (ex: registros de DB)
        # json_schema_extra pode ser útil para exemplos na documentação Swagger UI
        json_schema_extra = {
            "examples": [
                {
                    "is_valid": True,
                    "dado_normalizado": "Avenida Paulista, 1578 - Cerqueira César, São Paulo/SP - 01310-200",
                    "mensagem": "Endereço validado e normalizado com sucesso.",
                    "origem_validacao": "address_validator",
                    "details": {
                        "cep_validation": {
                            "input_original": "01310200",
                            "cleaned_data": "01310-200",
                            "message": "CEP válido e encontrado.",
                            "origem_validacao": "via_cep",
                            "validation_code": "CEP_001",
                            "address_found": True,
                            "external_api_data": {
                                "cep": "01310-200",
                                "logradouro": "Avenida Paulista",
                                "complemento": "de 1560 a 1980 - lado par",
                                "bairro": "Cerqueira César",
                                "localidade": "São Paulo",
                                "uf": "SP",
                                "ibge": "3550308",
                                "gia": "1004",
                                "ddd": "11",
                                "siafi": "7107"
                            }
                        },
                        "confidence_score": 0.95
                    },
                    "business_rule_applied": {
                        "code": "BR_ADDR_001",
                        "description": "Validação básica de CEP e preenchimento mínimo.",
                        "type": "DataQuality"
                    }
                },
                {
                    "is_valid": False,
                    "dado_normalizado": None,
                    "mensagem": "CEP inválido ou não encontrado.",
                    "origem_validacao": "address_validator",
                    "details": {
                        "cep_validation": {
                            "input_original": "00000000",
                            "cleaned_data": "00000-000",
                            "message": "CEP não encontrado.",
                            "origem_validacao": "via_cep",
                            "validation_code": "CEP_002",
                            "address_found": False,
                            "api_error": "CEP not found in external API."
                        }
                    },
                    "business_rule_applied": {
                        "code": "BR_ADDR_002",
                        "description": "Rejeição por CEP não encontrado.",
                        "type": "DataQuality"
                    }
                }
            ]
        }
        # Permite que o modelo seja convertido para JSON com atributos de classe
        json_encoders = {
            str: lambda v: v,  # Garante que strings sejam serializadas corretamente
            int: lambda v: v,  # Garante que inteiros sejam serializados corretamente
            float: lambda v: v,  # Garante que floats sejam serializados corretamente
            bool: lambda v: v,  # Garante que booleanos sejam serializados corretamente
            dict: lambda v: v,  # Garante que dicionários sejam serializados corretamente
            list: lambda v: v   # Garante que listas sejam serializadas corretamente
        }