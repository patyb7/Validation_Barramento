import logging
import asyncpg
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field, UUID4

logger = logging.getLogger(__name__)

# 1. Defina o SQL para CRIAR AS TABELAS
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS validation_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dado_original TEXT NOT NULL, -- CORRIGIDO: Alterado de VARCHAR(255) para TEXT
    dado_normalizado TEXT NOT NULL, -- CORRIGIDO: Alterado de VARCHAR(255) para TEXT
    mensagem TEXT,
    origem_validacao VARCHAR(100),
    tipo_validacao VARCHAR(100) NOT NULL,
    is_valido BOOLEAN NOT NULL DEFAULT FALSE,
    data_validacao TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    app_name VARCHAR(100) NOT NULL,
    client_identifier VARCHAR(255),
    regra_negocio_codigo VARCHAR(255),
    regra_negocio_descricao TEXT,
    regra_negocio_tipo VARCHAR(255),
    regra_negocio_parametros JSONB,
    validation_details JSONB DEFAULT '{}',
    is_golden_record BOOLEAN DEFAULT FALSE,
    golden_record_id UUID,
    usuario_criacao VARCHAR(255),
    usuario_atualizacao VARCHAR(255),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    short_id_alias VARCHAR(100),
    status_qualificacao VARCHAR(50),
    last_enrichment_attempt_at TIMESTAMP WITH TIME ZONE,
    client_entity_id VARCHAR(255)
);

-- Nova tabela para logs de auditoria
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp_evento TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    tipo_evento VARCHAR(100) NOT NULL,
    app_origem VARCHAR(100) NOT NULL,
    usuario_operador VARCHAR(255),
    record_id_afetado UUID, -- Referência ao ID da tabela validation_records
    client_entity_id_afetado VARCHAR(255), -- ID da entidade do cliente afetada
    detalhes_evento_json JSONB DEFAULT '{}',
    status_operacao VARCHAR(50) NOT NULL, -- SUCESSO, FALHA, AVISO
    mensagem_log TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Novo campo adicionado aqui
);

-- Tabela client_entities também deve ser criada aqui
CREATE TABLE IF NOT EXISTS client_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    main_document_normalized VARCHAR(255) NOT NULL,
    cclub VARCHAR(255),
    relationship_type VARCHAR(100),
    golden_record_cpf_cnpj_id UUID,
    golden_record_address_id UUID,
    golden_record_phone_id UUID,
    golden_record_email_id UUID,
    golden_record_cep_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    contributing_apps JSONB DEFAULT '{}'
);
"""

# 2. Defina o SQL para CRIAR ÍNDICES
CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_validation_records_tipo_validacao ON validation_records (tipo_validacao);
CREATE INDEX IF NOT EXISTS idx_validation_records_app_name ON validation_records (app_name);
CREATE INDEX IF NOT EXISTS idx_validation_records_data_validacao ON validation_records (data_validacao DESC);
-- Índices para busca por dado original/normalizado e tipo/app para Golden Record
CREATE INDEX IF NOT EXISTS idx_validation_records_dado_original_tipo_app ON validation_records (dado_original, tipo_validacao, app_name);
CREATE INDEX IF NOT EXISTS idx_validation_records_dado_normalizado_tipo_app ON validation_records (dado_normalizado, tipo_validacao, app_name);
CREATE INDEX IF NOT EXISTS idx_validation_records_is_golden_record ON validation_records (is_golden_record);
CREATE INDEX IF NOT EXISTS idx_validation_records_client_entity_id ON validation_records (client_entity_id); -- Índice correto para client_entity_id na tabela validation_records

-- Índices para a nova tabela audit_logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp_evento DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tipo_evento ON audit_logs (tipo_evento);
CREATE INDEX IF NOT EXISTS idx_audit_logs_app_origem ON audit_logs (app_origem);
CREATE INDEX IF NOT EXISTS idx_audit_logs_record_id_afetado ON audit_logs (record_id_afetado);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at DESC); -- Novo índice adicionado aqui

-- Índices para a tabela client_entities
CREATE INDEX IF NOT EXISTS idx_client_entities_main_document_normalized ON client_entities (main_document_normalized);
CREATE INDEX IF NOT EXISTS idx_client_entities_cclub ON client_entities (cclub);
CREATE UNIQUE INDEX IF NOT EXISTS idx_client_entities_main_document_cclub_unique ON client_entities (main_document_normalized, COALESCE(cclub, '')); -- Índice de unicidade
"""

# 3. Defina o SQL para CRIAR A FUNÇÃO (para atualização automática de updated_at)
CREATE_UPDATE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# 4. Defina o SQL para CRIAR OS TRIGGERS (para atualização automática de updated_at)
CREATE_TRIGGERS_SQL = """
-- Trigger para validation_records
DROP TRIGGER IF EXISTS trg_validation_records_updated_at ON validation_records;
CREATE TRIGGER trg_validation_records_updated_at
BEFORE UPDATE ON validation_records
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger para client_entities
DROP TRIGGER IF EXISTS trg_client_entities_updated_at ON client_entities;
CREATE TRIGGER trg_client_entities_updated_at
BEFORE UPDATE ON client_entities
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

async def initialize_database(db_manager): # AGORA RECEBE O DatabaseManager INTEIRO
    """
    Inicializa o esquema do banco de dados, criando as tabelas, índices,
    funções e triggers se não existirem.
    """
    try:
        logger.info("Executando DDL para criar tabelas, indices e triggers se nao existirem...")

        # CORREÇÃO: Usa db_manager.get_connection() para obter uma conexão do pool
        async with db_manager.get_connection() as conn:
            # 1. Executa a criação das tabelas (agora inclui audit_logs e client_entities)
            await conn.execute(CREATE_TABLES_SQL)
            logger.info("Tabelas 'validation_records', 'audit_logs' e 'client_entities' verificadas/criadas.")

            # 2. Executa a criação dos índices (agora inclui audit_logs e client_entities)
            await conn.execute(CREATE_INDEXES_SQL)
            logger.info("Índices para 'validation_records', 'audit_logs' e 'client_entities' verificados/criados.")

            # 3. Executa a criação da função de update_at
            await conn.execute(CREATE_UPDATE_FUNCTION_SQL)
            logger.info("Função 'update_updated_at_column' verificada/criada.")

            # 4. Executa a criação dos triggers de update_at (agora inclui client_entities)
            await conn.execute(CREATE_TRIGGERS_SQL)
            logger.info("Triggers 'trg_validation_records_updated_at' e 'trg_client_entities_updated_at' verificadas/criadas.")

        logger.info("Esquema do banco de dados verificado/inicializado com sucesso.")

    except asyncpg.exceptions.PostgresError as e:
        logger.critical(f"Falha CRÍTICA ao inicializar o esquema do banco de dados (asyncpg): {e}", exc_info=True)
        raise
    except Exception as e:
        logger.critical(f"Erro inesperado durante a inicialização do banco de dados (geral): {e}", exc_info=True)
        raise

# A definição do modelo Pydantic está em app/api/schemas/common.py e app/models/validation_record.py
# (Se esta classe já existe em app/models/validation_record.py, esta cópia aqui é apenas para referência
# e deve ser removida do arquivo schema.py final, mantendo apenas a definição do schema SQL).
class ValidationRecord(BaseModel):
    id: Optional[UUID4] = None
    dado_original: str
    dado_normalizado: str
    mensagem: Optional[str] = None
    origem_validacao: Optional[str] = None
    tipo_validacao: str
    is_valido: bool = Field(default=False, alias="is_valid")
    data_validacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    app_name: str
    client_identifier: Optional[str] = None
    regra_negocio_codigo: Optional[str] = None
    regra_negocio_descricao: Optional[str] = None
    regra_negocio_tipo: Optional[str] = None
    regra_negocio_parametros: Optional[Dict[str, Any]] = None
    validation_details: Dict[str, Any] = Field(default_factory=dict)
    is_golden_record: bool = False
    golden_record_id: Optional[UUID4] = None
    usuario_criacao: Optional[str] = None
    usuario_atualizacao: Optional[str] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    short_id_alias: Optional[str] = None
    status_qualificacao: Optional[str] = None
    last_enrichment_attempt_at: Optional[datetime] = None
    client_entity_id: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u)
        }
