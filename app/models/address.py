# app/models/address.py

from pydantic import BaseModel, Field, conint, conlist
from typing import Optional, Dict, Any, List

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
    input_original: Optional[str] = None
    cleaned_data: Optional[str] = None
    message: str
    origem_validacao: str
    validation_code: str
    address_found: Optional[bool] = None
    external_api_data: Optional[Dict[str, Any]] = None
    api_error: Optional[str] = None
    external_api_response_raw: Optional[Dict[str, Any]] = None

class AddressValidationResult(BaseModel):
    """Modelo Pydantic para o resultado da validação de endereço."""
    is_valid: bool = Field(..., description="Se o endereço é considerado válido.")
    dado_normalizado: Optional[str] = Field(None, description="O endereço normalizado em uma string formatada.")
    mensagem: str = Field(..., description="Mensagem explicativa do resultado.")
    origem_validacao: str = Field("address_validator", description="Fonte da validação.")
    details: Dict[str, Any] = Field(..., description="Detalhes adicionais (validação de CEP, etc.).")
    business_rule_applied: Dict[str, Any] = Field(..., description="Detalhes da regra de negócio aplicada.")

    # Sobrescreve o tipo de 'cep_validation' dentro de 'details' para CEPValidationDetails
    # Note: Pydantic v2 permite aninhamento direto, mas para dicts genéricos é preciso cuidado.
    # No entanto, para um dict 'details' que tem uma chave específica, podemos validar o conteúdo
    # do CEPValidationDetails em tempo de execução na lógica do validador, e o campo aqui
    # continua sendo Dict[str, Any] para flexibilidade, ou podemos usar Pydantic.model_validate
    # no validador para converter o resultado do CEPValidator.
    # Por simplicidade, vamos manter details como Dict[str, Any] e garantir a estrutura na lógica.