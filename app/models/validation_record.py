import json
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class ValidationRecord(BaseModel):
    """
    Modelo Pydantic para um registro completo de validação armazenado no banco de dados.
    Corresponde à estrutura da tabela 'validacoes_gerais'.
    """
    id: Optional[int] = Field(None, description="ID único do registro de validação (gerado pelo DB).")
    dado_original: str = Field(..., description="O dado fornecido originalmente para validação.")
    dado_normalizado: Optional[str] = Field(None, description="O dado após normalização, se aplicável.")
    
    # *** ALTERAÇÃO CRÍTICA AQUI: Mudei o nome do campo para 'is_valido'
    # para que ele corresponda diretamente à coluna do banco de dados.
    # Isso elimina a necessidade do 'alias'.
    is_valido: bool = Field(..., description="Indica se o dado foi considerado válido.")
    
    mensagem: str = Field(..., description="Mensagem descritiva do resultado da validação.")
    origem_validacao: str = Field(..., description="Sistema ou componente que executou a validação (ex: 'lib_google_phone', 'servico_interno').")
    tipo_validacao: str = Field(..., description="O tipo de validação realizada (ex: 'telefone', 'cep', 'email', 'cpf').")
    app_name: str = Field(..., description="Nome da aplicação que solicitou a validação.")
    client_identifier: Optional[str] = Field(None, description="Identificador único do cliente da aplicação que solicitou a validação.")
    
    # Campos para regras de negócio aplicadas
    regra_negocio_codigo: Optional[str] = Field(None, description="Código da regra de negócio que resultou na decisão final, se aplicável.")
    regra_negocio_descricao: Optional[str] = Field(None, description="Descrição da regra de negócio aplicada.")
    regra_negocio_tipo: Optional[str] = Field(None, description="Tipo da regra de negócio (ex: 'bloqueio', 'alerta', 'permitido').")
    regra_negocio_parametros: Optional[Dict[str, Any]] = Field(None, description="Parâmetros da regra de negócio aplicada, em formato JSON.")
    
    validation_details: Dict[str, Any] = Field({}, description="Detalhes adicionais da validação em formato JSON.")
    
    data_validacao: datetime = Field(default_factory=datetime.now, description="Timestamp da realização da validação.")
    created_at: datetime = Field(default_factory=datetime.now, description="Timestamp de criação do registro no DB.")
    updated_at: datetime = Field(default_factory=datetime.now, description="Timestamp da última atualização do registro no DB.")
    
    usuario_criacao: Optional[str] = Field(None, description="Usuário ou sistema que criou o registro.")
    usuario_atualizacao: Optional[str] = Field(None, description="Usuário ou sistema que atualizou o registro pela última vez.")

    is_deleted: bool = Field(False, description="Flag para exclusão lógica do registro.")
    deleted_at: Optional[datetime] = Field(None, description="Timestamp da exclusão lógica do registro.")

    class Config:
        # ISSO É CRUCIAL para que o Pydantic 2.x possa ler os atributos de objetos como asyncpg.Record
        # Ele tentará mapear automaticamente nomes de colunas para nomes de campos.
        from_attributes = True 
        
        # Como o nome do campo agora é 'is_valido', não precisamos mais de 'populate_by_name = True' 
        # especificamente para lidar com o alias, embora possa ser mantido se houver outras razões.
        # populate_by_name = True 

        # Removido 'json_encoders' conforme discutido para Pydantic v2
        json_schema_extra = {
            "example": {
                "id": 123,
                "dado_original": "+5511987654321",
                "dado_normalizado": "5511987654321",
                "is_valido": True, # *** AQUI NO EXAMPLE TAMBÉM DEVE SER 'is_valido'
                "mensagem": "Número de telefone válido e formatado.",
                "origem_validacao": "lib_google_phone_number",
                "tipo_validacao": "telefone",
                "app_name": "app_cliente_x",
                "client_identifier": "ID_CLIENTE_ABC",
                "regra_negocio_codigo": "REGRA_TEL_NACIONAL",
                "regra_negocio_descricao": "Telefone válido para operação nacional.",
                "regra_negocio_tipo": "permitido",
                "regra_negocio_parametros": {"regiao": "nacional", "operadora_preferencial": "tim"},
                "validation_details": {"carrier": "Vivo", "location": "São Paulo", "is_mobile": True},
                "data_validacao": "2025-06-16T09:00:00.000000",
                "created_at": "2025-06-16T09:00:00.000000",
                "updated_at": "2025-06-16T09:00:00.000000",
                "usuario_criacao": "sistema_validacao",
                "usuario_atualizacao": "operador_api",
                "is_deleted": False,
                "deleted_at": None
            }
        }