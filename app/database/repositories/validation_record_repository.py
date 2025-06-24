# app/database/repositories/validation_record_repository.py

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
import asyncpg # Importa asyncpg diretamente para os tipos de exceção e conexão
from app.database.manager import DatabaseManager
from app.models.validation_record import ValidationRecord # Importa o modelo ValidationRecord
from datetime import datetime, timezone
import uuid # Importa uuid para uuid.uuid4()
import json # Importar a biblioteca json

logger = logging.getLogger(__name__)

class ValidationRecordRepository:
    """
    Gerencia as operações de persistência para registros de validação no banco de dados.
    """
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        logger.info("ValidationRecordRepository inicializado.")

    async def create_record(self, record: ValidationRecord) -> Optional[ValidationRecord]:
        """
        Cria um novo registro de validação no banco de dados.
        """
        # Garante que timestamps e UUIDs são definidos antes da inserção, se ainda não estiverem.
        # O banco de dados também pode definir defaults, mas é mais seguro fazer aqui.
        if not record.id:
            record.id = uuid.uuid4()
        if not record.created_at:
            record.created_at = datetime.now(timezone.utc)
        if not record.updated_at:
            record.updated_at = datetime.now(timezone.utc)
        if not record.short_id_alias and record.id: # Garante que o alias é gerado se o ID existe
            record.short_id_alias = record.generate_short_id_alias()

        insert_sql = """
            INSERT INTO validation_records (
                id, dado_original, dado_normalizado, is_valido, mensagem,
                origem_validacao, tipo_validacao, app_name, client_identifier,
                short_id_alias, validation_details, data_validacao,
                regra_negocio_codigo, regra_negocio_descricao, regra_negocio_tipo,
                regra_negocio_parametros, usuario_criacao, usuario_atualizacao,
                is_deleted, deleted_at, is_golden_record, golden_record_id,
                status_qualificacao, last_enrichment_attempt_at, client_entity_id, created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27
            ) RETURNING *;
        """
        # CONVERSÃO PARA JSON STRING ao INSERIR:
        validation_details_json = record.validation_details.copy() if record.validation_details is not None else {}
        regra_negocio_parametros_json = record.regra_negocio_parametros.copy() if record.regra_negocio_parametros is not None else None

        params = (
            record.id,
            record.dado_original,
            record.dado_normalizado,
            record.is_valido,
            record.mensagem,
            record.origem_validacao,
            record.tipo_validacao,
            record.app_name,
            record.client_identifier,
            record.short_id_alias,
            json.dumps(validation_details_json), # CONVERTIDO PARA JSON STRING
            record.data_validacao,
            record.regra_negocio_codigo,
            record.regra_negocio_descricao,
            record.regra_negocio_tipo,
            json.dumps(regra_negocio_parametros_json) if regra_negocio_parametros_json is not None else None, # CONVERTIDO PARA JSON STRING
            record.usuario_criacao,
            record.usuario_atualizacao,
            record.is_deleted,
            record.deleted_at,
            record.is_golden_record,
            record.golden_record_id,
            record.status_qualificacao,
            record.last_enrichment_attempt_at,
            record.client_entity_id,
            record.created_at,
            record.updated_at
        )
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(insert_sql, *params)
                if row:
                    logger.debug(f"DEBUG: Row returned from DB: {row}")
                    logger.debug(f"DEBUG: Type of row: {type(row)}")
                    
                    # CONVERSÃO EXPLÍCITA ao LER: Converter asyncpg.Record para dict e, se JSONB for string, carregar
                    row_as_dict = dict(row)
                    if isinstance(row_as_dict.get('validation_details'), str):
                        row_as_dict['validation_details'] = json.loads(row_as_dict['validation_details'])
                    if isinstance(row_as_dict.get('regra_negocio_parametros'), str):
                        row_as_dict['regra_negocio_parametros'] = json.loads(row_as_dict['regra_negocio_parametros'])

                    logger.debug(f"DEBUG: Row as dict (after JSON loads): {row_as_dict}")
                    logger.debug(f"DEBUG: Type of row as dict (after JSON loads): {type(row_as_dict)}")
                    return ValidationRecord.model_validate(row_as_dict) # Validar o dicionário
                return None
        except asyncpg.exceptions.NotNullViolationError as e:
            logger.error(f"Erro ao criar registro no banco de dados: {e}\nDETAIL: {e.detail}")
            return None
        except asyncpg.exceptions.UniqueViolationError as e:
            logger.error(f"Erro de violação de unicidade ao criar registro: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao criar registro de validação: {e}", exc_info=True)
            return None

    async def get_record_by_id(self, record_id: UUID) -> Optional[ValidationRecord]:
        """
        Recupera um registro de validação pelo seu ID.
        """
        select_sql = "SELECT * FROM validation_records WHERE id = $1;"
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(select_sql, record_id)
                if row:
                    row_as_dict = dict(row)
                    if isinstance(row_as_dict.get('validation_details'), str):
                        row_as_dict['validation_details'] = json.loads(row_as_dict['validation_details'])
                    if isinstance(row_as_dict.get('regra_negocio_parametros'), str):
                        row_as_dict['regra_negocio_parametros'] = json.loads(row_as_dict['regra_negocio_parametros'])
                    return ValidationRecord.model_validate(row_as_dict)
                return None
        except Exception as e:
            logger.error(f"Erro ao buscar registro por ID {record_id}: {e}", exc_info=True)
            return None

    async def get_records_by_app_name(self, app_name: str, limit: int = 10, include_deleted: bool = False) -> List[ValidationRecord]:
        """
        Recupera registros de validação por nome da aplicação.
        """
        sql = "SELECT * FROM validation_records WHERE app_name = $1"
        params = [app_name]
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        sql += " ORDER BY data_validacao DESC LIMIT $2;"
        params.append(limit)

        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(sql, *params)
                # CONVERSÃO EXPLÍCITA ao LER:
                processed_rows = []
                for row in rows:
                    row_as_dict = dict(row)
                    if isinstance(row_as_dict.get('validation_details'), str):
                        row_as_dict['validation_details'] = json.loads(row_as_dict['validation_details'])
                    if isinstance(row_as_dict.get('regra_negocio_parametros'), str):
                        row_as_dict['regra_negocio_parametros'] = json.loads(row_as_dict['regra_negocio_parametros'])
                    processed_rows.append(ValidationRecord.model_validate(row_as_dict))
                return processed_rows
        except Exception as e:
            logger.error(f"Erro ao buscar histórico para app '{app_name}': {e}", exc_info=True)
            return []

    async def soft_delete_record(self, record_id: UUID) -> bool:
        """
        Marca um registro como logicamente deletado.
        """
        update_sql = """
            UPDATE validation_records
            SET is_deleted = TRUE, deleted_at = NOW(), updated_at = NOW()
            WHERE id = $1 AND is_deleted = FALSE;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                result = await conn.execute(update_sql, record_id)
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Erro ao executar soft delete para o registro {record_id}: {e}", exc_info=True)
            return False

    async def restore_record(self, record_id: UUID) -> bool:
        """
        Restaura um registro que foi logicamente deletado.
        """
        update_sql = """
            UPDATE validation_records
            SET is_deleted = FALSE, deleted_at = NULL, updated_at = NOW()
            WHERE id = $1 AND is_deleted = TRUE;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                result = await conn.execute(update_sql, record_id)
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Erro ao restaurar registro {record_id}: {e}", exc_info=True)
            return False

    async def find_duplicate_record(self, dado_normalizado: str, tipo_validacao: str, app_name: str, exclude_record_id: Optional[UUID] = None) -> Optional[ValidationRecord]:
        """
        Procura um registro duplicado baseado no dado normalizado, tipo e nome da aplicação,
        excluindo opcionalmente um ID específico.
        Considera apenas registros NÃO deletados logicamente.
        """
        sql = """
            SELECT * FROM validation_records
            WHERE dado_normalizado = $1
            AND tipo_validacao = $2
            AND app_name = $3
            AND is_deleted = FALSE
        """
        params = [dado_normalizado, tipo_validacao, app_name]

        if exclude_record_id:
            sql += " AND id != $4"
            params.append(exclude_record_id)
        
        sql += " LIMIT 1;" # Apenas o primeiro duplicado é suficiente

        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(sql, *params)
                if row:
                    row_as_dict = dict(row)
                    if isinstance(row_as_dict.get('validation_details'), str):
                        row_as_dict['validation_details'] = json.loads(row_as_dict['validation_details'])
                    if isinstance(row_as_dict.get('regra_negocio_parametros'), str):
                        row_as_dict['regra_negocio_parametros'] = json.loads(row_as_dict['regra_negocio_parametros'])
                    return ValidationRecord.model_validate(row_as_dict)
                return None
        except Exception as e:
            logger.error(f"Erro ao buscar duplicata para {dado_normalizado}/{tipo_validacao}/{app_name}: {e}", exc_info=True)
            return None

    async def find_golden_record(self, dado_normalizado: str, tipo_validacao: str) -> Optional[ValidationRecord]:
        """
        Procura o Golden Record para um dado normalizado e tipo de validação específicos.
        Considera apenas registros NÃO deletados logicamente.
        """
        sql = """
            SELECT * FROM validation_records
            WHERE dado_normalizado = $1
            AND tipo_validacao = $2
            AND is_golden_record = TRUE
            AND is_deleted = FALSE
            LIMIT 1;
        """
        params = [dado_normalizado, tipo_validacao]

        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(sql, *params)
                if row:
                    row_as_dict = dict(row)
                    if isinstance(row_as_dict.get('validation_details'), str):
                        row_as_dict['validation_details'] = json.loads(row_as_dict['validation_details'])
                    if isinstance(row_as_dict.get('regra_negocio_parametros'), str):
                        row_as_dict['regra_negocio_parametros'] = json.loads(row_as_dict['regra_negocio_parametros'])
                    return ValidationRecord.model_validate(row_as_dict)
                return None
        except Exception as e:
            logger.error(f"Erro ao buscar Golden Record para {dado_normalizado}/{tipo_validacao}: {e}", exc_info=True)
            return None

    async def update_golden_record_status(self, record_id: UUID, is_golden: bool, golden_record_id: Optional[UUID]) -> bool:
        """
        Atualiza o status is_golden_record e golden_record_id de um registro.
        """
        update_sql = """
            UPDATE validation_records
            SET is_golden_record = $2, golden_record_id = $3, updated_at = NOW()
            WHERE id = $1;
        """
        params = [record_id, is_golden, golden_record_id]
        try:
            async with self.db_manager.get_connection() as conn:
                result = await conn.execute(update_sql, *params)
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Erro ao atualizar status Golden Record para {record_id}: {e}", exc_info=True)
            return False

    async def update_record(self, record_id: UUID, updates: Dict[str, Any]) -> bool:
        """
        Atualiza campos específicos de um registro de validação.
        Args:
            record_id (UUID): O ID do registro a ser atualizado.
            updates (Dict[str, Any]): Um dicionário de campos para atualizar e seus novos valores.
        Returns:
            bool: True se a atualização for bem-sucedida, False caso contrário.
        """
        if not updates:
            return False # Nenhuma atualização para fazer

        set_clauses = []
        params = []
        param_counter = 1

        updates["updated_at"] = datetime.now(timezone.utc) # Sempre atualiza o timestamp

        for field, value in updates.items():
            set_clauses.append(f"{field} = ${param_counter}")
            # CONVERSÃO PARA JSON STRING para campos JSONB que podem estar em 'updates'
            if field in ["validation_details", "regra_negocio_parametros"] and isinstance(value, dict):
                params.append(json.dumps(value))
            else:
                params.append(value)
            param_counter += 1
        
        # Adiciona o ID ao final dos parâmetros para a cláusula WHERE
        set_clauses_str = ", ".join(set_clauses)
        update_sql = f"UPDATE validation_records SET {set_clauses_str} WHERE id = ${param_counter};"
        params.append(record_id)

        try:
            async with self.db_manager.get_connection() as conn:
                result = await conn.execute(update_sql, *params)
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Erro ao atualizar registro {record_id} com updates {updates}: {e}", exc_info=True)
            return False

    async def get_all_records_by_normalized_data(self, dado_normalizado: str, tipo_validacao: str) -> List[ValidationRecord]:
        """
        Retorna todos os registros para um dado normalizado e tipo de validação específicos.
        """
        select_sql = """
            SELECT * FROM validation_records
            WHERE dado_normalizado = $1
            AND tipo_validacao = $2
            ORDER BY data_validacao DESC;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(select_sql, dado_normalizado, tipo_validacao)
                # CONVERSÃO EXPLÍCITA ao LER:
                processed_rows = []
                for row in rows:
                    row_as_dict = dict(row)
                    if isinstance(row_as_dict.get('validation_details'), str):
                        row_as_dict['validation_details'] = json.loads(row_as_dict['validation_details'])
                    if isinstance(row_as_dict.get('regra_negocio_parametros'), str):
                        row_as_dict['regra_negocio_parametros'] = json.loads(row_as_dict['regra_negocio_parametros'])
                    processed_rows.append(ValidationRecord.model_validate(row_as_dict))
                return processed_rows
        except Exception as e:
            logger.error(f"Erro ao buscar registros por dado normalizado {dado_normalizado} e tipo {tipo_validacao}: {e}", exc_info=True)
            return []
