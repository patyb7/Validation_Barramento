# app/models/validation_record.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timezone

class ValidationRecord(BaseModel):
    """
    Modelo Pydantic para representar um registro de validação de dados
    a ser armazenado no banco de dados. Reflete o esquema da tabela 'validation_records'.
    Ajustado para o 'client_entity_id' ser gerado internamente pelo barramento.
    """
    id: Optional[int] = Field(None, description="ID único do registro de validação (gerado pelo DB).")
    dado_original: str = Field(..., description="O dado fornecido originalmente para validação.")
    dado_normalizado: Optional[str] = Field(None, description="O dado após normalização, se aplicável.")
    is_valido: bool = Field(..., description="Indica se o dado foi considerado válido.")
    is_golden_record: Optional[bool] = Field(default=False, description="Indica se este registro é considerado o 'golden record' ou a melhor fonte para este dado normalizado.")
    golden_record_id: Optional[int] = Field(default=None, description="Se este registro não for o golden, ID do registro que é o golden.")
    mensagem: str = Field(..., description="Mensagem descritiva do resultado da validação.")
    origem_validacao: str = Field(..., description="Sistema ou componente que executou a validação (ex: 'lib_google_phone', 'servico_interno').")
    tipo_validacao: str = Field(..., description="O tipo de validação realizada (ex: 'telefone', 'cep', 'email', 'cpf_cnpj').")
    app_name: str = Field(..., description="Nome da aplicação que solicitou a validação.")
    client_identifier: Optional[str] = Field(None, description="Identificador único do cliente da aplicação que solicitou a validação.")
    
    # Campo 'client_entity_id' agora será gerado internamente e armazenado.
    client_entity_id: Optional[str] = Field(None, description="ID interno do barramento para a entidade de cliente, gerado com base em client_identifier, dado_normalizado e cclub (se aplicável).") 
    
    # Campos para regras de negócio aplicadas
    regra_negocio_codigo: Optional[str] = Field(None, description="Código da regra de negócio que resultou na decisão final, se aplicável.")
    regra_negocio_descricao: Optional[str] = Field(None, description="Descrição da regra de negócio aplicada.")
    regra_negocio_tipo: Optional[str] = Field(None, description="Tipo da regra de negócio (ex: 'bloqueio', 'alerta', 'permitido').")
    regra_negocio_parametros: Optional[Dict[str, Any]] = Field(None, description="Parâmetros da regra de negócio aplicada, em formato JSON.")
    
    validation_details: Dict[str, Any] = Field(default_factory=dict, description="Detalhes adicionais da validação em formato JSON.")
    
    data_validacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp da realização da validação.")
    
    created_at: Optional[datetime] = Field(None, description="Timestamp de criação do registro no DB.") 
    updated_at: Optional[datetime] = Field(None, description="Timestamp da última atualização do registro no DB.")
    
    usuario_criacao: str = Field(..., description="Usuário ou sistema que criou o registro.")
    usuario_atualizacao: Optional[str] = Field(None, description="Usuário ou sistema que atualizou o registro pela última vez.")

    is_deleted: bool = Field(False, description="Flag para exclusão lógica do registro.")
    deleted_at: Optional[datetime] = Field(None, description="Timestamp da exclusão lógica do registro.")

    status_qualificacao: str = Field("NAO_QUALIFICADO", description="Status de qualificação do dado (e.g., 'NAO_QUALIFICADO', 'QUALIFICADO_MANUAL', 'QUALIFICADO_AUTOMATICO', 'ERRO_QUALIFICACAO').")
    last_enrichment_attempt_at: Optional[datetime] = Field(None, description="Timestamp da última tentativa de enriquecimento externo do dado.")

    class Config:
        from_attributes = True 
        populate_by_name = True 

        json_schema_extra = {
            "example": {
                "id": 123,
                "dado_original": "+5511987654321",
                "dado_normalizado": "5511987654321",
                "is_valido": True,
                "mensagem": "Número de telefone válido e formatado.",
                "origem_validacao": "lib_google_phone_number",
                "tipo_validacao": "telefone",
                "app_name": "app_cliente_x",
                "client_identifier": "ID_CLIENTE_ABC",
                "client_entity_id": "ab7cd8e9f...", # Exemplo de ID gerado pelo barramento
                "regra_negocio_codigo": "REGRA_TEL_NACIONAL",
                "regra_negocio_descricao": "Telefone válido para operação nacional.",
                "regra_negocio_tipo": "permitido",
                "regra_negocio_parametros": {"regiao": "nacional", "operadora_preferencial": "tim"},
                "validation_details": {"carrier": "Vivo", "location": "São Paulo", "is_mobile": True},
                "data_validacao": "2025-06-16T09:00:00.000000Z",
                "created_at": "2025-06-16T09:00:00.000000Z",
                "updated_at": "2025-06-16T09:00:00.000000Z",
                "usuario_criacao": "sistema_validacao",
                "usuario_atualizacao": "operador_api",
                "is_deleted": False,
                "deleted_at": None,
                "status_qualificacao": "NAO_QUALIFICADO",
                "last_enrichment_attempt_at": None
            }
        }
#             "status": "success",
#             "data": {
#                 "is_valid": True,
#                 "dado_normalizado": "12345678900",
#                 "mensagem": "CPF válido.",
#                 "origem_validacao": "lib_cpf_validator",
#                 "details": {
#                     "document_type": "CPF",
#                     "country": "BR",
#                     "is_valid_checksum": True
#                 },
#                 "business_rule_applied": {
#                     "rule_code": "CPF_VALIDATION",
#                     "rule_description": "Validação de CPF com checksum",
#                     "rule_type": "validation",
#                     "parameters": {
#                         "country": "BR",
#                         "document_type": "CPF"
#                     }
#                 }
#             }
#         }
#         }
#             "business_rule_applied": business_rule_applied
#         }
#         }