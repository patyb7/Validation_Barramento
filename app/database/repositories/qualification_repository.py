# app/database/repositories/qualification_repository.py

import logging
import uuid
import asyncpg
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

# Importar o DatabaseManager para obter conexões
from app.database.manager import DatabaseManager
# Importar os modelos Pydantic definidos anteriormente
from app.models.qualificacao_pendente import QualificacaoPendente, InvalidosQualificados
from app.models.validation_record import ValidationRecord # Necessário para buscar detalhes

logger = logging.getLogger(__name__)

class QualificationRepository:
    """
    Repositório para gerenciar a persistência de registros em:
    - qualificacoes_pendentes (registros aguardando revalidação/qualificação)
    - invalidos_desqualificados (registros que foram desqualificados ou falharam em todas as tentativas)
    - client_entities (os Golden Records consolidados)
    """
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        logger.info("QualificationRepository inicializado.")

    async def create_pending_qualification(self, pending_record: QualificacaoPendente) -> Optional[QualificacaoPendente]:
        """
        Adiciona um novo registro à tabela 'qualificacoes_pendentes'.
        """
        insert_sql = """
            INSERT INTO qualificacoes_pendentes (
                id, validation_record_id, client_identifier, validation_type,
                status_motivo, attempt_count, last_attempt_at, scheduled_next_attempt_at,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
            ) RETURNING *;
        """
        params = (
            pending_record.id,
            pending_record.validation_record_id,
            pending_record.client_identifier,
            pending_record.validation_type,
            pending_record.status_motivo,
            pending_record.attempt_count,
            pending_record.last_attempt_at,
            pending_record.scheduled_next_attempt_at,
            pending_record.created_at,
            pending_record.updated_at
        )
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(insert_sql, *params)
                if row:
                    logger.info(f"Registro de qualificação pendente criado: {pending_record.id} para record {pending_record.validation_record_id}")
                    return QualificacaoPendente.model_validate(row)
            return None
        except asyncpg.exceptions.UniqueViolationError:
            logger.warning(f"Tentativa de criar qualificacao_pendente duplicada para validation_record_id: {pending_record.validation_record_id}")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar registro de qualificação pendente para record {pending_record.validation_record_id}: {e}", exc_info=True)
            return None

    async def get_pending_qualifications_for_revalidation(self, limit: int = 100) -> List[QualificacaoPendente]:
        """
        Retorna registros de qualificação pendentes que estão prontos para revalidação.
        Pronto para revalidação significa: scheduled_next_attempt_at <= agora.
        """
        select_sql = """
            SELECT * FROM qualificacoes_pendentes
            WHERE scheduled_next_attempt_at <= $1
            ORDER BY scheduled_next_attempt_at ASC
            LIMIT $2;
        """
        now = datetime.now(timezone.utc)
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(select_sql, now, limit)
                return [QualificacaoPendente.model_validate(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao buscar registros pendentes para revalidação: {e}", exc_info=True)
            return []

    async def update_pending_qualification(self, pending_record: QualificacaoPendente) -> Optional[QualificacaoPendente]:
        """
        Atualiza um registro existente em 'qualificacoes_pendentes'.
        """
        update_sql = """
            UPDATE qualificacoes_pendentes
            SET
                attempt_count = $1,
                last_attempt_at = $2,
                scheduled_next_attempt_at = $3,
                updated_at = $4,
                status_motivo = $5
            WHERE id = $6
            RETURNING *;
        """
        params = (
            pending_record.attempt_count,
            pending_record.last_attempt_at,
            pending_record.scheduled_next_attempt_at,
            datetime.now(timezone.utc), # Força o updated_at para agora
            pending_record.status_motivo,
            pending_record.id
        )
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(update_sql, *params)
                if row:
                    logger.info(f"Registro de qualificação pendente atualizado: {pending_record.id}")
                    return QualificacaoPendente.model_validate(row)
            return None
        except Exception as e:
            logger.error(f"Erro ao atualizar registro de qualificação pendente {pending_record.id}: {e}", exc_info=True)
            return None

    async def delete_pending_qualification(self, pending_id: uuid.UUID) -> bool:
        """
        Remove um registro da tabela 'qualificacoes_pendentes' (após sucesso ou falha definitiva).
        """
        delete_sql = "DELETE FROM qualificacoes_pendentes WHERE id = $1;"
        try:
            async with self.db_manager.get_connection() as conn:
                status = await conn.execute(delete_sql, pending_id)
                if status == "DELETE 1":
                    logger.info(f"Registro de qualificação pendente {pending_id} removido.")
                    return True
            return False
        except Exception as e:
            logger.error(f"Erro ao remover registro de qualificação pendente {pending_id}: {e}", exc_info=True)
            return False

    async def create_invalid_record_archive(self, invalid_record: InvalidosQualificados) -> Optional[InvalidosQualificados]:
        """
        Adiciona um registro à tabela 'invalidos_desqualificados'.
        """
        insert_sql = """
            INSERT INTO invalidos_desqualificados (
                id, validation_record_id, client_identifier, reason_for_invalidation, archived_at
            ) VALUES (
                $1, $2, $3, $4, $5
            ) RETURNING *;
        """
        params = (
            invalid_record.id,
            invalid_record.validation_record_id,
            invalid_record.client_identifier,
            invalid_record.reason_for_invalidation,
            invalid_record.archived_at
        )
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(insert_sql, *params)
                if row:
                    logger.info(f"Registro arquivado como inválido: {invalid_record.id} para record {invalid_record.validation_record_id}")
                    return InvalidosQualificados.model_validate(row)
            return None
        except asyncpg.exceptions.UniqueViolationError:
            logger.warning(f"Tentativa de arquivar invalidos_desqualificados duplicado para validation_record_id: {invalid_record.validation_record_id}")
            return None
        except Exception as e:
            logger.error(f"Erro ao arquivar registro inválido para record {invalid_record.validation_record_id}: {e}", exc_info=True)
            return None

    async def get_invalid_record_archive(self, validation_record_id: uuid.UUID) -> Optional[InvalidosQualificados]:
        """
        Busca um registro no arquivo de inválidos pelo ID do validation_record original.
        """
        select_sql = "SELECT * FROM invalidos_desqualificados WHERE validation_record_id = $1;"
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(select_sql, validation_record_id)
                if row:
                    return InvalidosQualificados.model_validate(row)
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar registro inválido por validation_record_id {validation_record_id}: {e}", exc_info=True)
            return None

    # --- Métodos para interagir com a tabela client_entities (Golden Records) ---
    async def get_client_entity_by_main_document(self, main_document_normalized: str) -> Optional[Dict[str, Any]]:
        """
        Busca um Golden Record existente na tabela client_entities pelo documento principal normalizado (CPF/CNPJ).
        """
        select_sql = """
            SELECT * FROM client_entities
            WHERE main_document_normalized = $1;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(select_sql, main_document_normalized)
                if row:
                    # Retorna o dicionário raw ou pode ser um modelo Pydantic ClientEntity se você criar um
                    return dict(row)
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar client_entity por documento principal: {e}", exc_info=True)
            return None

    async def create_client_entity(self, client_entity_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Cria um novo Golden Record na tabela 'client_entities'.
        client_entity_data deve ser um dicionário com os campos da tabela.
        """
        insert_sql = """
            INSERT INTO client_entities (
                main_document_normalized,
                golden_record_cpf_cnpj_id,
                golden_record_address_id,
                golden_record_phone_id,
                golden_record_email_id,
                golden_record_cep_id,
                consolidated_data,
                relationship_type,
                cclub,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
            ) RETURNING *;
        """
        params = (
            client_entity_data.get("main_document_normalized"),
            client_entity_data.get("golden_record_cpf_cnpj_id"),
            client_entity_data.get("golden_record_address_id"),
            client_entity_data.get("golden_record_phone_id"),
            client_entity_data.get("golden_record_email_id"),
            client_entity_data.get("golden_record_cep_id"),
            client_entity_data.get("consolidated_data", {}), # Garantir que é um dict para JSONB
            client_entity_data.get("relationship_type"),
            client_entity_data.get("cclub"),
            datetime.now(timezone.utc),
            datetime.now(timezone.utc)
        )
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(insert_sql, *params)
                if row:
                    logger.info(f"Golden Record criado para {client_entity_data.get('main_document_normalized')}: {row['id']}")
                    return dict(row)
            return None
        except asyncpg.exceptions.UniqueViolationError:
            logger.warning(f"Tentativa de criar Golden Record duplicado para main_document_normalized: {client_entity_data.get('main_document_normalized')}")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar Golden Record para {client_entity_data.get('main_document_normalized')}: {e}", exc_info=True)
            return None

    async def update_client_entity(self, client_entity_id: uuid.UUID, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Atualiza um Golden Record existente na tabela 'client_entities'.
        update_data deve ser um dicionário com os campos a serem atualizados.
        """
        set_clauses = []
        params = []
        param_counter = 1

        for key, value in update_data.items():
            if key in ["main_document_normalized", "created_at", "id"]: # Não permitir update desses campos via este método
                continue
            set_clauses.append(f"{key} = ${param_counter}")
            params.append(value)
            param_counter += 1
        
        if not set_clauses:
            logger.warning(f"Nenhum campo para atualizar para client_entity_id {client_entity_id}.")
            return None

        update_sql = f"""
            UPDATE client_entities
            SET {', '.join(set_clauses)}
            WHERE id = ${param_counter}
            RETURNING *;
        """
        params.append(client_entity_id)

        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(update_sql, *params)
                if row:
                    logger.info(f"Golden Record atualizado para ID {client_entity_id}")
                    return dict(row)
            return None
        except Exception as e:
            logger.error(f"Erro ao atualizar Golden Record {client_entity_id}: {e}", exc_info=True)
            return None

    async def get_validation_record_details(self, record_id: uuid.UUID) -> Optional[ValidationRecord]:
        """
        Recupera os detalhes de um ValidationRecord específico.
        Necessário para o QualificationService pegar os dados para revalidação.
        """
        select_sql = """
            SELECT * FROM validation_records WHERE id = $1;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(select_sql, record_id)
                if row:
                    return ValidationRecord.model_validate(row)
            return None
        except Exception as e:
            logger.error(f"Erro ao obter detalhes do ValidationRecord {record_id}: {e}", exc_info=True)
            return None
