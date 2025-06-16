# app/database/schema.py

import logging
import asyncpg
from .manager import DatabaseManager

# Importações para o Pydantic BaseModel
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# O script SQL para criar a tabela, diretamente no código ou lido de um arquivo
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS validacoes_gerais (
    id SERIAL PRIMARY KEY,
    regra_negocio_tipo VARCHAR(50),
    regra_negocio_descricao TEXT,
    regra_negocio_parametros JSONB,
    usuario_criacao VARCHAR(255),
    usuario_atualizacao VARCHAR(255),
    dado_original VARCHAR(255) NOT NULL,
    dado_normalizado VARCHAR(255),
    mensagem TEXT,
    origem_validacao VARCHAR(100),
    tipo_validacao VARCHAR(50) NOT NULL,
    is_valido BOOLEAN NOT NULL, -- Mantido "is_valido" para evitar conflito com "valido" se ambos forem campos
    data_validacao TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    app_name VARCHAR(100) NOT NULL,
    client_identifier VARCHAR(255),
    regra_negocio_codigo VARCHAR(50),
    validation_details JSONB DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Opcional: Adicionar índices para otimizar buscas
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_tipo_validacao ON validacoes_gerais (tipo_validacao);
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_app_name ON validacoes_gerais (app_name);
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_data_validacao ON validacoes_gerais (data_validacao DESC);
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_dado_original_tipo_app ON validacoes_gerais (dado_original, tipo_validacao, app_name);
CREATE INDEX IF NOT EXISTS idx_validacoes_gerais_dado_normalizado_tipo_app ON validacoes_gerais (dado_normalizado, tipo_validacao, app_name);

-- Opcional: Adicionar função e trigger para atualizar 'updated_at' automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validacoes_gerais_updated_at ON validacoes_gerais;
CREATE TRIGGER trg_validacoes_gerais_updated_at
BEFORE UPDATE ON validacoes_gerais
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
"""

async def initialize_database(db_manager: DatabaseManager):
    """
    Cria as tabelas necessárias no banco de dados se elas ainda não existirem.
    Esta função é assíncrona e deve ser chamada com 'await'.
    """
    conn = None
    try:
        conn = await db_manager.get_connection() 
        logger.info("Executando DDL para criar tabela 'validacoes_gerais', índices e triggers se não existirem...")
        await conn.execute(CREATE_TABLE_SQL) 
        logger.info("Tabela 'validacoes_gerais' e objetos de banco de dados verificados/criados com sucesso.")
    except asyncpg.exceptions.PostgresError as e: 
        logger.critical(f"Erro CRÍTICO ao inicializar o banco de dados (asyncpg): {e}", exc_info=True)
        raise 
    except Exception as e:
        logger.critical(f"Erro inesperado durante a inicialização do banco de dados: {e}", exc_info=True)
        raise 
    finally:
        if conn:
            await db_manager.put_connection(conn)


### **Definição do Modelo Pydantic para `ValidationRecord`**

# Este modelo representa a tabela 'validacoes_gerais' e é usado para validação de dados.
class ValidationRecord(BaseModel):
    id: Optional[int] = None # SERIAL PRIMARY KEY é auto-incremento
    regra_negocio_tipo: Optional[str] = None # VARCHAR(50)
    regra_negocio_descricao: Optional[str] = None # TEXT
    regra_negocio_parametros: Optional[Dict[str, Any]] = Field(default_factory=dict) # JSONB
    usuario_criacao: str # VARCHAR(255) NOT NULL
    usuario_atualizacao: str # VARCHAR(255) NOT NULL
    dado_original: str # VARCHAR(255) NOT NULL
    dado_normalizado: Optional[str] = None # VARCHAR(255)
    is_valido: bool # BOOLEAN NOT NULL (usando este campo, se for o que realmente quer)
    mensagem: Optional[str] = None # TEXT
    origem_validacao: Optional[str] = None # VARCHAR(100)
    tipo_validacao: str # VARCHAR(50) NOT NULL
    data_validacao: Optional[datetime] = None # TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    app_name: str # VARCHAR(100) NOT NULL
    client_identifier: Optional[str] = None # VARCHAR(255)
    regra_negocio_codigo: Optional[str] = None # VARCHAR(50)
    validation_details: Dict[str, Any] = Field(default_factory=dict) # JSONB DEFAULT '{}'
    is_deleted: Optional[bool] = False # BOOLEAN DEFAULT FALSE
    deleted_at: Optional[datetime] = None # TIMESTAMP WITH TIME ZONE
    created_at: Optional[datetime] = None # TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    updated_at: Optional[datetime] = None # TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP

    # Adicione a configuração para permitir atributos extras, caso o Record do asyncpg traga algo a mais
    class Config:
        extra = "ignore" # Permite campos extras que não estão no modelo sem erro
        from_attributes = True # Pydantic v2: permite criar modelo a partir de objetos com atributos (como asyncpg.Record se convertido para dict, ou diretamente se ele tivesse __dict__)

# Você tinha uma classe vazia ValidationRequest, se ela não for usada, pode remover.
# Se for usada para Pydantic de entrada, defina-a aqui.
# class ValidationRequest:
#    pass