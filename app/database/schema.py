# app/database/schema.py
import asyncpg
import logging
import json # Importa json para manipular dados JSONB

# Configuração básica de logging para este módulo
logger = logging.getLogger(__name__)

# --- Definições de DDL (Data Definition Language) ---
# Agrupa todos os comandos SQL para criação de tabelas em uma única string
CREATE_TABLES_SQL = """
-- Cria a tabela validation_records se não existir
CREATE TABLE IF NOT EXISTS validation_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Usando UUID como PK
    dado_original TEXT NOT NULL,
    dado_normalizado TEXT,
    is_valido BOOLEAN NOT NULL,
    mensagem TEXT,
    origem_validacao VARCHAR(50) NOT NULL,
    tipo_validacao VARCHAR(50) NOT NULL,
    app_name VARCHAR(100) NOT NULL,
    client_identifier TEXT,
    validation_details JSONB,
    data_validacao TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Campos de regras de negócio (desnormalizados para facilitar consulta)
    regra_negocio_codigo VARCHAR(50),
    regra_negocio_descricao TEXT,
    regra_negocio_tipo VARCHAR(50),
    regra_negocio_parametros JSONB,

    -- Gerenciamento de ciclo de vida e Golden Record
    usuario_criacao TEXT,
    usuario_atualizacao TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_golden_record BOOLEAN NOT NULL DEFAULT FALSE, -- Indica se este registro é o Golden Record
    golden_record_id UUID, -- ID do Golden Record (pode ser o próprio ID ou de outro registro), alterado para UUID
    status_qualificacao VARCHAR(50), -- Por exemplo, 'QUALIFIED', 'UNQUALIFIED', 'PENDING'
    last_enrichment_attempt_at TIMESTAMPTZ, -- Timestamp da última tentativa de enriquecimento
    client_entity_id TEXT -- ID da entidade cliente, se aplicável
    -- Removida a cláusula WHERE da UNIQUE constraint aqui, será adicionada como um índice único parcial
    -- UNIQUE (dado_normalizado, tipo_validacao, app_name, client_identifier) WHERE is_deleted = FALSE
);

-- Cria a tabela api_keys se não existir
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Alterado para UUID
    api_key_hash TEXT NOT NULL UNIQUE, -- Armazena o hash da chave, não a chave em texto claro
    app_name VARCHAR(100) NOT NULL,
    access_level VARCHAR(50) NOT NULL, -- Ex: 'standard', 'admin', 'psdc', 'mdm'
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    permissions JSONB DEFAULT '{}'::jsonb -- Ex: {"can_delete_records": true, "can_check_duplicates": true}
);

-- Cria a tabela business_rules se não existir
CREATE TABLE IF NOT EXISTS business_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Alterado para UUID
    rule_code VARCHAR(50) NOT NULL UNIQUE,
    rule_description TEXT NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- Ex: 'phone', 'document', 'address', 'email', 'global'
    criteria JSONB NOT NULL DEFAULT '{}'::jsonb, -- Condições para aplicação da regra
    actions JSONB NOT NULL DEFAULT '{}'::jsonb, -- Ações a serem tomadas quando a regra é aplicada
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 100, -- Prioridade de aplicação (menor número = maior prioridade)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cria a tabela golden_records_metadata para rastrear Golden Records por tipo de dado
CREATE TABLE IF NOT EXISTS golden_records_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Alterado para UUID
    dado_normalizado TEXT NOT NULL,
    tipo_validacao VARCHAR(50) NOT NULL,
    golden_record_id UUID NOT NULL, -- ID do registro em validation_records que é o GR, alterado para UUID
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dado_normalizado, tipo_validacao) -- Garante um único GR por dado normalizado/tipo
);
"""

# Agrupa todos os comandos SQL para criação de índices em uma única string
CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_validation_records_type_normalized ON validation_records (tipo_validacao, dado_normalizado);
CREATE INDEX IF NOT EXISTS idx_validation_records_app_name ON validation_records (app_name);
CREATE INDEX IF NOT EXISTS idx_validation_records_is_valid ON validation_records (is_valido);
CREATE INDEX IF NOT EXISTS idx_validation_records_is_deleted ON validation_records (is_deleted);
CREATE INDEX IF NOT EXISTS idx_validation_records_golden_record_id ON validation_records (golden_record_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_api_key_hash ON api_keys (api_key_hash);
CREATE INDEX IF NOT EXISTS idx_business_rules_rule_type ON business_rules (rule_type);

-- Adicionada esta linha para criar o índice único parcial
CREATE UNIQUE INDEX IF NOT EXISTS uix_validation_records_active_unique ON validation_records (dado_normalizado, tipo_validacao, app_name, client_identifier) WHERE is_deleted = FALSE;
"""

# Agrupa todos os comandos SQL para criação de funções e triggers em uma única string
CREATE_TRIGGERS_SQL = """
-- Função genérica para atualizar 'updated_at' ou 'last_updated_at'
CREATE OR REPLACE FUNCTION update_timestamp_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW(); -- Assume 'updated_at' como nome padrão
    IF TG_TABLE_NAME = 'golden_records_metadata' THEN -- Lida com 'last_updated_at' para golden_records_metadata
        NEW.last_updated_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para a tabela validation_records
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_validation_records_updated_at') THEN
        CREATE TRIGGER set_validation_records_updated_at
        BEFORE UPDATE ON validation_records
        FOR EACH ROW
        EXECUTE FUNCTION update_timestamp_column();
    END IF;
END
$$;

-- Trigger para a tabela api_keys
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_api_keys_updated_at') THEN
        CREATE TRIGGER set_api_keys_updated_at
        BEFORE UPDATE ON api_keys
        FOR EACH ROW
        EXECUTE FUNCTION update_timestamp_column();
    END IF;
END
$$;

-- Trigger para a tabela business_rules
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_business_rules_updated_at') THEN
        CREATE TRIGGER set_business_rules_updated_at
        BEFORE UPDATE ON business_rules
        FOR EACH ROW
        EXECUTE FUNCTION update_timestamp_column();
    END IF;
END
$$;

-- Trigger para a tabela golden_records_metadata
-- Note que a função update_timestamp_column já foi modificada para lidar com 'last_updated_at'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_golden_records_metadata_updated_at') THEN
        CREATE TRIGGER set_golden_records_metadata_updated_at
        BEFORE UPDATE ON golden_records_metadata
        FOR EACH ROW
        EXECUTE FUNCTION update_timestamp_column();
    END IF;
END
$$;
"""

async def initialize_database_schema(conn: asyncpg.Connection):
    """
    Verifica e inicializa o esquema do banco de dados, criando tabelas, índices e triggers
    se eles ainda não existirem.

    Esta função recebe uma conexão 'asyncpg.Connection' já ativa e a utiliza
    para executar os comandos DDL.
    """
    logger.info("Executando DDL para criar tabelas, índices e triggers se não existirem...")
    
    try:
        # Executa a DDL para criar tabelas
        await conn.execute(CREATE_TABLES_SQL)
        logger.info("Tabelas verificadas/criadas.")

        # Executa a DDL para criar índices
        await conn.execute(CREATE_INDEXES_SQL)
        logger.info("Índices verificados/criados.")

        # Executa a DDL para criar funções e triggers
        await conn.execute(CREATE_TRIGGERS_SQL)
        logger.info("Funções e Triggers verificados/criados.")

        logger.info("DDL de inicialização do banco de dados concluído com sucesso.")

    except asyncpg.exceptions.PostgresError as e:
        logger.critical(f"Erro no PostgreSQL durante a inicialização do banco de dados: {e}", exc_info=True)
        raise # Re-lança a exceção para que o startup da aplicação falhe
    except Exception as e:
        logger.critical(f"Erro inesperado durante a inicialização do banco de dados: {e}", exc_info=True)
        raise # Re-lança a exceção
