# app/database/schema.py

import logging
import asyncpg
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from app.database.manager import DatabaseManager

logger = logging.getLogger(__name__)

CREATE_SCHEMA_SQL = """
-- Tabela para ClientEntity
CREATE TABLE IF NOT EXISTS client_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Usando UUID nativo com default para nova criação
    main_document_normalized VARCHAR(255) NOT NULL UNIQUE,
    cclub VARCHAR(255),
    relationship_type VARCHAR(50),
    -- Golden Record IDs aqui referenciam validacoes_gerais, FKs serão adicionadas abaixo
    golden_record_cpf_cnpj_id INTEGER, 
    golden_record_address_id INTEGER,
    golden_record_phone_id INTEGER,
    golden_record_email_id INTEGER,
    golden_record_cep_id INTEGER,
    contributing_apps JSONB DEFAULT '{}', -- Armazena Dict[str, datetime]
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices para client_entities
CREATE INDEX IF NOT EXISTS idx_client_entities_main_document_normalized ON client_entities (main_document_normalized);
CREATE INDEX IF NOT EXISTS idx_client_entities_cclub ON client_entities (cclub);

-- Tabela para ValidationRecord
CREATE TABLE IF NOT EXISTS validacoes_gerais (
    id SERIAL PRIMARY KEY,
    regra_negocio_tipo VARCHAR(50),
    regra_negocio_descricao TEXT,
    regra_negocio_parametros JSONB DEFAULT '{}',
    usuario_criacao VARCHAR(255) NOT NULL,
    usuario_atualizacao VARCHAR(255),
    dado_original VARCHAR(255) NOT NULL,
    dado_normalizado VARCHAR(255),
    mensagem TEXT,
    origem_validacao VARCHAR(100),
    tipo_validacao VARCHAR(50) NOT NULL,
    is_valido BOOLEAN NOT NULL,
    data_validacao TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    app_name VARCHAR(100) NOT NULL,
    is_golden_record BOOLEAN DEFAULT FALSE,
    golden_record_id INTEGER, -- Apenas declara a coluna, a FK será adicionada depois
    client_identifier VARCHAR(255),
    regra_negocio_codigo VARCHAR(50),
    validation_details JSONB DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- NOVO CAMPO: Associação à ClientEntity
    client_entity_id UUID, -- Alterado para UUID, alinhado com o tipo do id em client_entities
    -- NOVOS CAMPOS PARA QUALIFICAÇÃO E ENRIQUECIMENTO
    status_qualificacao VARCHAR(50) DEFAULT 'NAO_QUALIFICADO' NOT NULL, -- Ex: 'NAO_QUALIFICADO', 'QUALIFICADO_MANUAL', 'QUALIFICADO_AUTOMATICO', 'ERRO_QUALIFICACAO'
    last_enrichment_attempt_at TIMESTAMP WITH TIME ZONE -- Quando o último enriquecimento foi tentado (pode ser NULL)
);

-- Opcional: Adicionar índices para otimizar buscas em validacoes_gerais
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_tipo_validacao ON validacoes_gerais (tipo_validacao);
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_app_name ON validacoes_gerais (app_name);
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_data_validacao ON validacoes_gerais (data_validacao DESC);
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_dado_original_tipo_app ON validacoes_gerais (dado_original, tipo_validacao, app_name);
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_dado_normalizado_tipo_app ON validacoes_gerais (dado_normalizado, tipo_validacao, app_name);
CREATE INDEX IF NOT EXISTS idx_dado_normalizado_tipo_validacao ON validacoes_gerais (dado_normalizado, tipo_validacao);
CREATE INDEX IF NOT EXISTS idx_is_golden_record ON validacoes_gerais (is_golden_record) WHERE is_golden_record = TRUE;
-- NOVO ÍNDICE para client_entity_id
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_client_entity_id ON validacoes_gerais (client_entity_id);
-- NOVOS ÍNDICES PARA QUALIFICAÇÃO/ENRIQUECIMENTO
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_status_qualificacao ON validacoes_gerais (status_qualificacao);
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_last_enrichment_attempt_at ON validacoes_gerais (last_enrichment_attempt_at);


-- Função para atualizar 'updated_at' automaticamente (reutilizável para ambas as tabelas)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Adicionar chaves estrangeiras para client_entities (após validacoes_gerais ser criada) com verificação de existência
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_golden_record_cpf_cnpj' AND conrelid = 'client_entities'::regclass) THEN
        ALTER TABLE client_entities ADD CONSTRAINT fk_golden_record_cpf_cnpj FOREIGN KEY (golden_record_cpf_cnpj_id) REFERENCES validacoes_gerais(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_golden_record_address' AND conrelid = 'client_entities'::regclass) THEN
        ALTER TABLE client_entities ADD CONSTRAINT fk_golden_record_address FOREIGN KEY (golden_record_address_id) REFERENCES validacoes_gerais(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_golden_record_phone' AND conrelid = 'client_entities'::regclass) THEN
        ALTER TABLE client_entities ADD CONSTRAINT fk_golden_record_phone FOREIGN KEY (golden_record_phone_id) REFERENCES validacoes_gerais(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_golden_record_email' AND conrelid = 'client_entities'::regclass) THEN
        ALTER TABLE client_entities ADD CONSTRAINT fk_golden_record_email FOREIGN KEY (golden_record_email_id) REFERENCES validacoes_gerais(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_golden_record_cep' AND conrelid = 'client_entities'::regclass) THEN
        ALTER TABLE client_entities ADD CONSTRAINT fk_golden_record_cep FOREIGN KEY (golden_record_cep_id) REFERENCES validacoes_gerais(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Adicionar chave estrangeira de validacoes_gerais para client_entities com verificação de existência
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_client_entity' AND conrelid = 'validacoes_gerais'::regclass) THEN
        ALTER TABLE validacoes_gerais ADD CONSTRAINT fk_client_entity FOREIGN KEY (client_entity_id) REFERENCES client_entities(id) ON DELETE SET NULL;
    END IF;
END $$;


-- Triggers para 'updated_at' com verificação de existência
-- A função update_updated_at_column é recriada com OR REPLACE, então não precisa de IF NOT EXISTS para a função em si.

DO $$
BEGIN
    -- Trigger para validacoes_gerais
    -- Primeiro, garantir que não haja trigger com o mesmo nome para evitar duplicidade ou erro ao recriar.
    -- DROP TRIGGER IF EXISTS trg_validacoes_gerais_updated_at ON validacoes_gerais; -- Não é necessário se a recriação estiver dentro do IF NOT EXISTS
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_validacoes_gerais_updated_at' AND tgrelid = 'validacoes_gerais'::regclass) THEN
        CREATE TRIGGER trg_validacoes_gerais_updated_at
        BEFORE UPDATE ON validacoes_gerais
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    -- Trigger para client_entities
    -- DROP TRIGGER IF EXISTS trg_client_entities_updated_at ON client_entities; -- Não é necessário se a recriação estiver dentro do IF NOT EXISTS
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_client_entities_updated_at' AND tgrelid = 'client_entities'::regclass) THEN
        CREATE TRIGGER trg_client_entities_updated_at
        BEFORE UPDATE ON client_entities
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;
"""

async def initialize_database_schema(db_manager: DatabaseManager):
    """
    Cria as tabelas necessárias no banco de dados se elas ainda não existirem.
    Esta função é assíncrona e deve ser chamada com 'await'.
    """
    conn = None
    try:
        conn = await db_manager.get_connection()
        logger.info("Executando DDL para criar tabelas, índices e triggers se não existirem...")
        # Executar a DDL completa, que agora inclui as verificações de existência
        await conn.execute(CREATE_SCHEMA_SQL) 
        logger.info("Tabelas e objetos de banco de dados verificados/criados com sucesso.")
    except asyncpg.exceptions.PostgresError as e:
        logger.critical(f"Erro CRÍTICO ao inicializar o banco de dados (asyncpg): {e}", exc_info=True)
        raise # Re-lança a exceção para que o FastAPI capture e encerre
    except Exception as e:
        logger.critical(f"Erro inesperado durante a inicialização do banco de dados: {e}", exc_info=True)
        raise # Re-lança a exceção
    finally:
        if conn:
            await db_manager.put_connection(conn)