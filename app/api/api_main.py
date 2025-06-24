# app/database/schema.py
import asyncpg
import logging
# Não precisamos mais importar DatabaseManager aqui se a função receberá a conexão diretamente
# from app.database.manager import DatabaseManager 

logger = logging.getLogger(__name__)

# A função agora recebe uma conexão asyncpg diretamente
# O parâmetro deve ser `conn` (ou qualquer nome que indique que é a conexão)
async def initialize_database_schema(conn: asyncpg.Connection): # <--- MUDANÇA ESSENCIAL AQUI
    """
    Garante que todas as tabelas, índices e triggers necessários existam no banco de dados.
    Esta função deve ser chamada na inicialização da aplicação, recebendo uma conexão já ativa.
    """
    logger.info("Executando DDL para criar tabelas, índices e triggers se não existirem...")
    
    try:
        # **REMOVA COMPLETAMENTE ESTE BLOCO**
        # async with db_manager.get_connection() as conn: 
        # Esta linha (e o bloco 'async with' associado) não são necessários aqui,
        # pois você já está recebendo uma conexão como argumento!
        
        # Agora, simplesmente use a 'conn' que foi passada para esta função
        # CREATE TABLE validation_records
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS validation_records (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            entity_id TEXT NOT NULL,
            validation_type VARCHAR(50) NOT NULL,
            data_value TEXT NOT NULL,
            validation_status VARCHAR(20) NOT NULL,
            rule_applied TEXT,
            validation_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            source_application TEXT,
            additional_info JSONB DEFAULT '{}',
            is_deleted BOOLEAN DEFAULT FALSE
        );
        """)
        logger.info("Tabela 'validation_records' verificada/criada.")

        # CREATE INDEXes
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_validation_records_entity_id ON validation_records (entity_id);
        """)
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_validation_records_validation_type ON validation_records (validation_type);
        """)
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_validation_records_status ON validation_records (validation_status);
        """)
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_validation_records_timestamp ON validation_records (validation_timestamp DESC);
        """)
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_validation_records_is_deleted ON validation_records (is_deleted);
        """)
        logger.info("Índices verificados/criados.")

        # CREATE TRIGGER FOR UPDATED_AT (se você quiser um campo updated_at)
        # Primeiro, crie a função para atualizar o timestamp
        await conn.execute("""
        CREATE OR REPLACE FUNCTION update_timestamp_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.validation_timestamp = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)
        logger.info("Função 'update_timestamp_column' verificada/criada.")

        # Então, crie o trigger
        await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_validation_records_timestamp') THEN
                CREATE TRIGGER set_validation_records_timestamp
                BEFORE UPDATE ON validation_records
                FOR EACH ROW
                EXECUTE FUNCTION update_timestamp_column();
                logger.info('Trigger "set_validation_records_timestamp" criado.');
            ELSE
                logger.info('Trigger "set_validation_records_timestamp" já existe.');
            END IF;
        END
        $$;
        """)

        logger.info("DDL de inicialização do banco de dados concluído com sucesso.")

    except Exception as e:
        logger.critical(f"Erro inesperado durante a inicialização do banco de dados: {e}", exc_info=True)
        raise # Re-lança a exceção para impedir que a aplicação inicie com um DB mal configurado.