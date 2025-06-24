from pydantic import BaseModel, Field, EmailStr, UUID4, validator
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, date, timezone
import uuid

# --- Schemas de Requisição (Input Models) ---

class PhoneValidationData(BaseModel):
    """Schema para dados de validação de telefone."""
    phone_number: str = Field(..., description="O número de telefone a ser validado.")
    country_hint: Optional[str] = Field("BR", description="Sugestão de código de país (ISO 3166-1 alpha-2, ex: BR, US).")

class CEPValidationData(BaseModel):
    """Schema para dados de validação de CEP."""
    cep: str = Field(..., description="O Código de Endereçamento Postal (CEP) a ser validado.")

class EmailValidationData(BaseModel):
    """Schema para dados de validação de e-mail."""
    email: EmailStr = Field(..., description="O endereço de e-mail a ser validado.")

class CpfCnpjValidationData(BaseModel):
    """Schema para dados de validação de CPF ou CNPJ."""
    document: str = Field(..., description="O CPF ou CNPJ a ser validado.")

class AddressValidationData(BaseModel):
    """Schema para dados de validação de endereço completo."""
    logradouro: str = Field(..., description="Nome da rua, avenida, etc.")
    numero: Optional[Union[str, int]] = Field(None, description="Número do imóvel.")
    complemento: Optional[str] = Field(None, description="Complemento do endereço.")
    bairro: str = Field(..., description="Nome do bairro.")
    cidade: str = Field(..., description="Nome da cidade.")
    estado: str = Field(..., min_length=2, max_length=2, description="Sigla do estado (ex: SP, RJ).")
    cep: Optional[str] = Field(None, description="CEP do endereço.")
    pais: Optional[str] = Field("BR", description="País do endereço (ISO 3166-1 alpha-2).")

class NomeValidationData(BaseModel):
    """Schema para validação de nome completo."""
    nome_completo: str = Field(..., description="O nome completo a ser validado.")

class SexoValidationData(BaseModel):
    """Schema para validação de gênero/sexo."""
    sexo: str = Field(..., description="O gênero/sexo a ser validado (ex: Masculino, Feminino, Outro).")

class RGValidationData(BaseModel):
    """Schema para validação de RG."""
    rg: str = Field(..., description="O número do RG a ser validado.")

class DataNascimentoValidationData(BaseModel):
    """Schema para validação de data de nascimento."""
    data_nascimento: str = Field(..., description="A data de nascimento a ser validado no formato DD/MM/YYYY.")

# NOVO: Modelo para validação de dados completos de uma pessoa
class PersonDataModel(BaseModel):
    """
    Schema para dados completos de uma pessoa, usado na validação 'pessoa_completa'.
    Contém todos os campos relevantes para o cadastro de uma pessoa.
    """
    nome: Optional[str] = Field(None, description="Nome completo da pessoa.")
    idade: Optional[int] = Field(None, description="Idade da pessoa.")
    cpf: Optional[str] = Field(None, description="Número do CPF.")
    rg: Optional[str] = Field(None, description="Número do RG.")
    data_nasc: Optional[str] = Field(None, description="Data de nascimento no formato DD/MM/YYYY.")
    sexo: Optional[str] = Field(None, description="Gênero/sexo da pessoa.")
    signo: Optional[str] = Field(None, description="Signo da pessoa.")
    mae: Optional[str] = Field(None, description="Nome da mãe.")
    pai: Optional[str] = Field(None, description="Nome do pai.")
    email: Optional[EmailStr] = Field(None, description="Endereço de e-mail.")
    senha: Optional[str] = Field(None, description="Senha (se aplicável, para validação de segurança).")
    cep: Optional[str] = Field(None, description="CEP do endereço principal.")
    endereco: Optional[str] = Field(None, description="Nome da rua/logradouro do endereço principal.")
    numero: Optional[Union[str, int]] = Field(None, description="Número do imóvel no endereço principal.")
    bairro: Optional[str] = Field(None, description="Bairro do endereço principal.")
    cidade: Optional[str] = Field(None, description="Cidade do endereço principal.")
    estado: Optional[str] = Field(None, min_length=2, max_length=2, description="Estado do endereço principal (sigla).")
    telefone_fixo: Optional[str] = Field(None, description="Número de telefone fixo.")
    celular: Optional[str] = Field(None, description="Número de telefone celular.")
    altura: Optional[str] = Field(None, description="Altura da pessoa (ex: '1,75').")
    peso: Optional[Union[int, float]] = Field(None, description="Peso da pessoa em kg.")
    tipo_sanguineo: Optional[str] = Field(None, description="Tipo sanguíneo (ex: A+, AB-).")
    cor: Optional[str] = Field(None, description="Cor da pessoa.")

    class Config:
        extra = "allow" # Permite campos adicionais que não estão explicitamente definidos aqui
        from_attributes = True

# ATUALIZADO: UniversalValidationRequest para incluir PersonDataModel na união
class UniversalValidationRequest(BaseModel):
    """
    Modelo de requisição universal para o endpoint de validação.
    'validation_type' especifica o tipo de dado a ser validado.
    'data' contém o payload específico para o tipo de validação.
    """
    validation_type: str = Field(..., description="O tipo de validação a ser realizada (ex: 'cpf_cnpj', 'telefone', 'pessoa_completa').")
    # A união deve listar os modelos mais específicos primeiro para um parsing mais eficiente
    data: Union[
        PersonDataModel, # Novo e mais abrangente, deve vir antes dos mais específicos se houver sobreposição
        PhoneValidationData,
        CEPValidationData,
        EmailValidationData,
        CpfCnpjValidationData,
        AddressValidationData,
        NomeValidationData,
        SexoValidationData,
        RGValidationData,
        DataNascimentoValidationData,
        Dict[str, Any] # Fallback genérico para qualquer outro dicionário
    ] = Field(..., description="O payload de dados para a validação específica.")
    client_identifier: Optional[str] = Field(None, description="Identificador do cliente ou sistema que está enviando a requisição.")
    operator_id: Optional[str] = Field(None, description="Identificador do operador ou usuário que iniciou a ação.")

# --- Schemas de Resposta (Output Models) ---

class ValidationResponse(BaseModel):
    """
    Modelo de resposta para o resultado de uma validação.
    Inclui o dado original, normalizado, status de validade, mensagem,
    detalhes da validação, e informações da regra de negócio aplicada.
    """
    id: UUID4 = Field(..., description="ID único do registro de validação.")
    dado_original: Union[str, Dict[str, Any]] = Field(..., description="O dado original fornecido para validação (pode ser JSON string ou dict).")
    dado_normalizado: Union[str, Dict[str, Any]] = Field(..., description="O dado após a normalização (pode ser JSON string ou dict).")
    is_valido: bool = Field(..., description="Indica se o dado é considerado válido.")
    mensagem: str = Field(..., description="Mensagem descritiva do resultado da validação.")
    origem_validacao: str = Field(..., description="Origem da validação (ex: 'phone_validator', 'cpf_cnpj_validator').")
    tipo_validacao: str = Field(..., description="Tipo de dado que foi validado (ex: 'telefone', 'cpf_cnpj', 'pessoa_completa').")
    app_name: str = Field(..., description="Nome da aplicação que realizou a validação.")
    client_identifier: Optional[str] = Field(None, description="Identificador do cliente associado à requisição.")
    short_id_alias: Optional[str] = Field(None, description="Um alias ou ID curto para o registro, se aplicável.")
    validation_details: Dict[str, Any] = Field(default_factory=dict, description="Detalhes adicionais da validação, em formato JSON.")
    data_validacao: datetime = Field(..., description="Timestamp da validação.")
    regra_negocio_codigo: Optional[str] = Field(None, description="Código da regra de negócio aplicada.")
    regra_negocio_descricao: Optional[str] = Field(None, description="Descrição da regra de negócio aplicada.")
    regra_negocio_tipo: Optional[str] = Field(None, description="Tipo da regra de negócio (ex: 'Telefone - Formato', 'CPF - Dígitos Verificadores').")
    regra_negocio_parametros: Optional[Dict[str, Any]] = Field(None, description="Parâmetros da regra de negócio, em formato JSON.")
    is_golden_record: bool = Field(..., description="Indica se o registro é um Golden Record.")
    golden_record_id: Optional[UUID4] = Field(None, description="ID do Golden Record associado, se aplicável.")
    status_qualificacao: Optional[str] = Field(None, description="Status de qualificação do dado (ex: 'PENDING', 'QUALIFIED').")
    last_enrichment_attempt_at: Optional[datetime] = Field(None, description="Timestamp da última tentativa de enriquecimento.")
    client_entity_id: Optional[str] = Field(None, description="ID da entidade cliente afetada (para logs).")
    status: str = Field("success", description="Status geral da resposta (success/error).")
    message: str = Field("Validação concluída.", description="Mensagem geral da resposta.")
    status_code: int = Field(200, description="Código HTTP de status da resposta.")

    @validator('data_validacao', 'last_enrichment_attempt_at', pre=True)
    def parse_datetime_fields(cls, value):
        if isinstance(value, str):
            # Tenta parsear strings ISO formatadas
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                pass
            # Tenta parsear strings sem fuso horário (assumindo UTC)
            try:
                return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        # Adicione tratamento para `date` se necessário
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
        return value

    @validator('id', 'golden_record_id', pre=True)
    def parse_uuid_fields(cls, value):
        if isinstance(value, str):
            try:
                return uuid.UUID(value)
            except ValueError:
                pass
        return value

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u)
        }
        json_dumps_mode = 'json'


class HistoryRecordResponse(BaseModel):
    """
    Modelo para representar um registro de histórico de validação.
    Simplificado para exibição no histórico.
    """
    id: UUID4 = Field(..., description="ID único do registro de validação.")
    dado_original: Union[str, Dict[str, Any]] = Field(..., description="O dado original fornecido para validação.")
    dado_normalizado: Union[str, Dict[str, Any]] = Field(..., description="O dado após a normalização.")
    is_valido: bool = Field(..., description="Indica se o dado é válido.")
    mensagem: str = Field(..., description="Mensagem do resultado.")
    tipo_validacao: str = Field(..., description="Tipo de dado validado.")
    data_validacao: datetime = Field(..., description="Timestamp da validação.")
    app_name: str = Field(..., description="Nome da aplicação.")
    client_identifier: Optional[str] = Field(None, description="Identificador do cliente.")
    is_golden_record: bool = Field(..., description="É um Golden Record?")
    short_id_alias: Optional[str] = Field(None, description="Alias ou ID curto.")
    is_deleted: bool = Field(False, description="Indica se o registro foi soft-deletado.")
    deleted_at: Optional[datetime] = Field(None, description="Timestamp do soft delete.")
    created_at: datetime = Field(..., description="Timestamp de criação do registro.")
    updated_at: datetime = Field(..., description="Timestamp da última atualização do registro.")
    client_entity_id: Optional[str] = Field(None, description="ID da entidade cliente afetada (para logs).")

    @validator('data_validacao', 'deleted_at', 'created_at', 'updated_at', pre=True)
    def parse_datetime_history_fields(cls, value):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                pass
            try:
                return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
        return value

    @validator('id', pre=True)
    def parse_uuid_history_fields(cls, value):
        if isinstance(value, str):
            try:
                return uuid.UUID(value)
            except ValueError:
                pass
        return value

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u)
        }
        json_dumps_mode = 'json'
