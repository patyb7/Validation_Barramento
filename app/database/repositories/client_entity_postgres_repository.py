import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import uuid # Importar uuid para usar o tipo uuid.UUID
import asyncpg # Driver assíncrono para PostgreSQL
from app.models.client_entity import ClientEntity # Importa o modelo Pydantic ClientEntity
from app.database.manager import DatabaseManager # Importa DatabaseManager para gerenciar conexões
logger = logging.getLogger(__name__)

class ClientEntityPostgresRepository:
    """
    Repositório para interagir com a tabela 'client_entities' no banco de dados PostgreSQL.
    Gerencia operações CRUD e consultas específicas para ClientEntity.
    """
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        logger.info("ClientEntityPostgresRepository inicializado.")

    def _row_to_client_entity(self, row: asyncpg.Record) -> Optional[ClientEntity]:
        """
        Método auxiliar privado para converter um asyncpg.Record em uma instância de ClientEntity.
        Lida com a desserialização de JSONB e a conversão de UUIDs.
        """
        if not row:
            return None
        
        entity_data = dict(row)
        entity_id_for_log = entity_data.get('id', 'N/A')

        # Convertendo UUIDs de asyncpg.Record (uuid.UUID object) para string para o Pydantic
        # O Pydantic ClientEntity espera UUID4
        for uuid_field in [
            'id', 'golden_record_cpf_cnpj_id', 'golden_record_address_id',
            'golden_record_phone_id', 'golden_record_email_id', 'golden_record_cep_id'
        ]:
            if uuid_field in entity_data and entity_data[uuid_field] is not None:
                entity_data[uuid_field] = str(entity_data[uuid_field])
            else:
                entity_data[uuid_field] = None # Garante None se for None no DB

        # Convertendo JSONB de asyncpg.Record (pode ser dict ou str) para dict Python
        # Para 'contributing_apps', se for string (vindo do DB), decodifica. Se for None, default para dict vazio.
        if 'contributing_apps' in entity_data:
            apps_data = entity_data['contributing_apps']
            if isinstance(apps_data, str):
                try:
                    # Converte timestamps string de volta para datetime
                    parsed_apps = json.loads(apps_data)
                    for app_name, timestamp_str in parsed_apps.items():
                        if isinstance(timestamp_str, str):
                            parsed_apps[app_name] = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
                    entity_data['contributing_apps'] = parsed_apps
                except (json.JSONDecodeError, ValueError):
                    logger.warning(f"Erro ao decodificar contributing_apps para ClientEntity ID {entity_id_for_log}. Definindo como vazio.")
                    entity_data['contributing_apps'] = {}
            elif apps_data is None:
                entity_data['contributing_apps'] = {}
        else:
            entity_data['contributing_apps'] = {}

        # Garantir que campos de data/hora sejam corretamente tipados (já são handled pelo asyncpg, mas para segurança)
        # created_at e updated_at já vêm como datetime com fuso horário do asyncpg
        # Não é necessário fazer nada extra aqui para eles.

        try:
            return ClientEntity(**entity_data)
        except Exception as pydantic_e:
            logger.error(f"Erro ao instanciar ClientEntity para ID {entity_id_for_log}: {pydantic_e}. Dados: {entity_data}", exc_info=True)
            return None

    async def get_by_id(self, entity_id: uuid.UUID) -> Optional[ClientEntity]:
        """Busca uma ClientEntity pelo seu ID (UUID) no PostgreSQL."""
        query_sql = """
        SELECT id, main_document_normalized, cclub, relationship_type,
               golden_record_cpf_cnpj_id, golden_record_address_id,
               golden_record_phone_id, golden_record_email_id, golden_record_cep_id,
               created_at, updated_at, contributing_apps
        FROM client_entities
        WHERE id = $1::uuid;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(query_sql, entity_id)
                return self._row_to_client_entity(row)
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao buscar ClientEntity pelo ID '{entity_id}' no DB: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar ClientEntity pelo ID '{entity_id}': {e}", exc_info=True)
            return None

    async def get_by_document_and_cclub(self, document_normalized: str, cclub: Optional[str]) -> Optional[ClientEntity]:
        """
        Busca uma ClientEntity pelo CPF/CNPJ principal normalizado e CCLUB no PostgreSQL.
        """
        # A cláusula WHERE precisa lidar com 'cclub' que pode ser NULL
        # Usamos `IS NOT DISTINCT FROM` para comparar valores que podem ser NULL.
        # `IS NOT DISTINCT FROM` trata NULL = NULL como TRUE e NULL = non-NULL as FALSE.
        query_sql = """
        SELECT id, main_document_normalized, cclub, relationship_type,
               golden_record_cpf_cnpj_id, golden_record_address_id,
               golden_record_phone_id, golden_record_email_id, golden_record_cep_id,
               created_at, updated_at, contributing_apps
        FROM client_entities
        WHERE main_document_normalized = $1
          AND cclub IS NOT DISTINCT FROM $2;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(query_sql, document_normalized, cclub)
                return self._row_to_client_entity(row)
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao buscar ClientEntity por documento '{document_normalized}' e CCLUB '{cclub}' no DB: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar ClientEntity por documento '{document_normalized}' e CCLUB '{cclub}': {e}", exc_info=True)
            return None

    async def save(self, client_entity: ClientEntity) -> ClientEntity:
        """
        Salva ou atualiza uma ClientEntity no PostgreSQL.
        Usa INSERT ... ON CONFLICT (id) DO UPDATE para lidar com upsert.
        """
        # Serializa o contributing_apps para JSON string, com tratamento para datetimes
        contributing_apps_json = json.dumps({
            app: dt.isoformat() for app, dt in client_entity.contributing_apps.items()
        }) if client_entity.contributing_apps else '{}'

        insert_sql = """
        INSERT INTO client_entities (
            id, main_document_normalized, cclub, relationship_type,
            golden_record_cpf_cnpj_id, golden_record_address_id,
            golden_record_phone_id, golden_record_email_id, golden_record_cep_id,
            created_at, updated_at, contributing_apps
        ) VALUES (
            $1::uuid, $2, $3, $4, $5::uuid, $6::uuid, $7::uuid, $8::uuid, $9::uuid,
            $10, $11, $12::jsonb
        )
        ON CONFLICT (id) DO UPDATE SET
            main_document_normalized = EXCLUDED.main_document_normalized,
            cclub = EXCLUDED.cclub,
            relationship_type = EXCLUDED.relationship_type,
            golden_record_cpf_cnpj_id = EXCLUDED.golden_record_cpf_cnpj_id,
            golden_record_address_id = EXCLUDED.golden_record_address_id,
            golden_record_phone_id = EXCLUDED.golden_record_phone_id,
            golden_record_email_id = EXCLUDED.golden_record_email_id,
            golden_record_cep_id = EXCLUDED.golden_record_cep_id,
            updated_at = NOW(), -- A trigger do DB também atualizaria, mas é bom explicitar
            contributing_apps = EXCLUDED.contributing_apps
        RETURNING id, created_at, updated_at;
        """
        
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(
                    insert_sql,
                    client_entity.id,
                    client_entity.main_document_normalized,
                    client_entity.cclub,
                    client_entity.relationship_type,
                    client_entity.golden_record_cpf_cnpj_id,
                    client_entity.golden_record_address_id,
                    client_entity.golden_record_phone_id,
                    client_entity.golden_record_email_id,
                    client_entity.golden_record_cep_id,
                    client_entity.created_at,
                    datetime.now(timezone.utc), # updated_at no insert/update
                    contributing_apps_json
                )
                if row:
                    # Atualiza os timestamps do modelo com os valores retornados pelo DB
                    client_entity.id = str(row['id'])
                    client_entity.created_at = row['created_at']
                    client_entity.updated_at = row['updated_at']
                    logger.info(f"ClientEntity salva/atualizada com sucesso no DB. ID: {client_entity.id}")
                    return client_entity
                return None
        except asyncpg.exceptions.UniqueViolationError as e:
            logger.error(f"Erro de violação de unicidade ao salvar ClientEntity: {e}", exc_info=True)
            # Isso ocorreria se houvesse uma restrição UNIQUE em (main_document_normalized, cclub)
            # e a inserção tentasse criar uma duplicata com um ID diferente.
            # O ON CONFLICT (id) trata apenas conflitos de PK.
            # Se a unicidade for nos campos de negócio, a lógica aqui precisaria ser mais elaborada
            # (ex: verificar duplicidade antes do save, ou usar ON CONFLICT na coluna de negócio)
            raise # Re-lançar para o serviço lidar com a duplicidade de negócio
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao salvar ClientEntity no DB: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar ClientEntity: {e}", exc_info=True)
            return None

    async def delete(self, entity_id: uuid.UUID) -> bool:
        """Deleta uma ClientEntity pelo seu ID (UUID) no PostgreSQL."""
        delete_sql = """
        DELETE FROM client_entities
        WHERE id = $1::uuid
        RETURNING id;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(delete_sql, entity_id)
                if row:
                    logger.info(f"ClientEntity {entity_id} deletada com sucesso do DB.")
                    return True
                logger.warning(f"Tentativa de deletar ClientEntity inexistente no DB: {entity_id}")
                return False
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao deletar ClientEntity {entity_id} no DB: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao deletar ClientEntity {entity_id}: {e}", exc_info=True)
            return False

# SQL para a criação da tabela client_entities (para referência)
# Você precisará executar este DDL no seu banco de dados 'Barramento'
# ou adicioná-lo ao seu script de inicialização de esquema (app/database/schema.py)
"""
CREATE TABLE IF NOT EXISTS client_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    main_document_normalized TEXT NOT NULL,
    cclub TEXT,
    relationship_type TEXT,
    golden_record_cpf_cnpj_id UUID,
    golden_record_address_id UUID,
    golden_record_phone_id UUID,
    golden_record_email_id UUID,
    golden_record_cep_id UUID,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    contributing_apps JSONB DEFAULT '{}'
);

-- Índices para otimizar buscas
CREATE INDEX IF NOT EXISTS idx_client_entities_main_document_normalized ON client_entities (main_document_normalized);
CREATE INDEX IF NOT EXISTS idx_client_entities_cclub ON client_entities (cclub);
CREATE INDEX IF NOT EXISTS idx_client_entities_doc_cclub ON client_entities (main_document_normalized, cclub);

-- Se você quiser garantir unicidade da combinação (documento, cclub) no DB
-- Mas cuidado: UNIQUE (col1, col2) em PostgreSQL permite múltiplos NULLs em col2 se não for em conjunto com col1.
-- Para unicidade onde NULLs são tratados como iguais para o propósito da restrição:
-- CREATE UNIQUE INDEX idx_unique_main_document_cclub_coalesce ON client_entities (main_document_normalized, COALESCE(cclub, ''));
-- Para o caso onde (DOC, NULL) é único e só pode aparecer uma vez:
-- CREATE UNIQUE INDEX idx_unique_main_document_cclub_null_only_one ON client_entities (main_document_normalized) WHERE cclub IS NULL;
-- CREATE UNIQUE INDEX idx_unique_main_document_cclub_not_null ON client_entities (main_document_normalized, cclub) WHERE cclub IS NOT NULL;
"""
import json # Importa json para serializar/deserializar JSONB