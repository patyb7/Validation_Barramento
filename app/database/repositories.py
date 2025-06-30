# app/database/repositories.py
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import asyncpg
import json
from app.database.manager import DatabaseManager
from app.models import ValidationRecord 
from pydantic import ValidationError

logger = logging.getLogger(__name__)

class ValidationRecordRepository:
    """
    Repositório para interagir com a tabela 'validacoes_gerais' no banco de dados.
    Gerencia operações CRUD para registros de validação, incluindo lógica de Golden Record.
    """
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        logger.info("ValidationRecordRepository inicializado.")

    def _row_to_validation_record(self, row: asyncpg.Record) -> ValidationRecord:
        """
        Converte uma linha (asyncpg.Record) do banco de dados para um modelo ValidationRecord.
        """
        record_dict = dict(row)

        try:
            record = ValidationRecord.model_validate(record_dict)
            return record
        except ValidationError as e:
            logger.error(f"Erro ao converter linha do DB para ValidationRecord (erro Pydantic): {e}. Linha: {record_dict}", exc_info=True)
            raise

    async def create_record(self, record: ValidationRecord) -> Optional[ValidationRecord]:
        """
        Insere um novo registro de validação no banco de dados.
        Recebe um objeto ValidationRecord.
        """
        query = """
            INSERT INTO validacoes_gerais (
                regra_negocio_tipo, regra_negocio_descricao, regra_negocio_parametros,
                usuario_criacao, usuario_atualizacao, dado_original, dado_normalizado,
                mensagem, origem_validacao, tipo_validacao, is_valido, data_validacao,
                app_name, client_identifier, regra_negocio_codigo, validation_details,
                is_deleted, deleted_at, is_golden_record, golden_record_id, client_entity_id,
                status_qualificacao, last_enrichment_attempt_at
            ) VALUES (
                $1, $2, $3::jsonb, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15::jsonb,
                $16, $17, $18, $19, $20, $21, $22, $23
            ) RETURNING *;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                inserted_row = await conn.fetchrow(
                    query,
                    record.regra_negocio_tipo, record.regra_negocio_descricao, json.dumps(record.regra_negocio_parametros),
                    record.usuario_criacao, record.usuario_atualizacao, record.dado_original, record.dado_normalizado,
                    record.mensagem, record.origem_validacao, record.tipo_validacao, record.is_valido, record.data_validacao,
                    record.app_name, record.client_identifier, record.regra_negocio_codigo, json.dumps(record.validation_details),
                    record.is_deleted, record.deleted_at,
                    record.is_golden_record, record.golden_record_id, record.client_entity_id,
                    record.status_qualificacao, record.last_enrichment_attempt_at
                )
                if inserted_row:
                    logger.info(f"Registro de validação inserido para {record.dado_original} (ID: {inserted_row['id']}).")
                    return self._row_to_validation_record(inserted_row)
                return None
        except Exception as e:
            logger.error(f"Erro ao inserir registro de validação: {e}", exc_info=True)
            raise

    async def update_record(self, record_id: int, record: ValidationRecord) -> Optional[ValidationRecord]:
        """
        Atualiza um registro de validação existente no banco de dados.
        Recebe um objeto ValidationRecord.
        """
        query = """
            UPDATE validacoes_gerais SET
                regra_negocio_tipo = $1,
                regra_negocio_descricao = $2,
                regra_negocio_parametros = $3::jsonb,
                usuario_atualizacao = $4,
                dado_original = $5,
                dado_normalizado = $6,
                mensagem = $7,
                origem_validacao = $8,
                tipo_validacao = $9,
                is_valido = $10,
                data_validacao = $11,
                app_name = $12,
                client_identifier = $13,
                regra_negocio_codigo = $14,
                validation_details = $15::jsonb,
                is_deleted = $16,
                deleted_at = $17,
                is_golden_record = $18,
                golden_record_id = $19,
                client_entity_id = $20,
                status_qualificacao = $21,
                last_enrichment_attempt_at = $22
                -- updated_at é definido pelo trigger trg_validacoes_gerais_updated_at
            WHERE id = $23
            RETURNING *;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                updated_row = await conn.fetchrow(
                    query,
                    record.regra_negocio_tipo, record.regra_negocio_descricao, json.dumps(record.regra_negocio_parametros),
                    record.usuario_atualizacao, record.dado_original, record.dado_normalizado,
                    record.mensagem, record.origem_validacao, record.tipo_validacao, record.is_valido, record.data_validacao,
                    record.app_name, record.client_identifier, record.regra_negocio_codigo, json.dumps(record.validation_details),
                    record.is_deleted, record.deleted_at,
                    record.is_golden_record, record.golden_record_id, record.client_entity_id,
                    record.status_qualificacao, record.last_enrichment_attempt_at,
                    record_id # ID do registro a ser atualizado
                )
                if updated_row:
                    logger.info(f"Registro de validação {record_id} atualizado com sucesso.")
                    return self._row_to_validation_record(updated_row)
                logger.warning(f"Nenhum registro encontrado com o ID {record_id} para atualização.")
                return None
        except Exception as e:
            logger.error(f"Erro ao atualizar registro de validação {record_id}: {e}", exc_info=True)
            raise

    async def get_record_by_id(self, record_id: int, include_deleted: bool = False) -> Optional[ValidationRecord]:
        """
        Busca um registro pelo seu ID, opcionalmente incluindo os deletados logicamente.
        """
        query_base = "SELECT * FROM validacoes_gerais WHERE id = $1"
        if not include_deleted:
            query_base += " AND is_deleted = FALSE"

        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(query_base, record_id)
                return self._row_to_validation_record(row) if row else None
        except Exception as e:
            logger.error(f"Erro ao buscar registro por ID {record_id} (include_deleted={include_deleted}): {e}", exc_info=True)
            return None

    async def get_all_records_by_normalized_data(self, dado_normalizado: str, tipo_validacao: str) -> List[ValidationRecord]:
        """
        Busca TODOS os registros para um dado normalizado e tipo, de QUALQUER app_name,
        excluindo os logicamente deletados.
        """
        query = """
            SELECT * FROM validacoes_gerais
            WHERE dado_normalizado = $1 AND tipo_validacao = $2 AND is_deleted = FALSE
            ORDER BY data_validacao DESC;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(query, dado_normalizado, tipo_validacao)
                return [self._row_to_validation_record(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao buscar todos os registros por dado normalizado '{dado_normalizado}' ({tipo_validacao}): {e}", exc_info=True)
            return []

    async def update_golden_record_status(self, record_id: int, is_golden: bool, golden_record_id: Optional[int] = None) -> Optional[ValidationRecord]:
        """
        Atualiza o status de golden record para um registro específico.
        """
        query = """
            UPDATE validacoes_gerais SET
                is_golden_record = $1,
                golden_record_id = $2,
                updated_at = NOW() -- Definido pelo DB trigger
            WHERE id = $3
            RETURNING *;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(query, is_golden, golden_record_id, record_id)
                return self._row_to_validation_record(row) if row else None
        except Exception as e:
            logger.error(f"Erro ao atualizar status de golden record para {record_id}: {e}", exc_info=True)
            raise

    async def set_golden_record_false_for_normalized_data(self, dado_normalizado: str, tipo_validacao: str, exclude_id: Optional[int] = None):
        """
        Define is_golden_record para FALSE para todos os registros
        de um dado normalizado e tipo, exceto um específico (que será o novo Golden Record).
        Não atualiza golden_record_id aqui, essa atualização deve ser feita para cada registro individualmente
        pelo ValidationService.
        """
        query_base = """
            UPDATE validacoes_gerais SET
                is_golden_record = FALSE,
                updated_at = NOW() -- Definido pelo DB trigger
            WHERE dado_normalizado = $1 AND tipo_validacao = $2
            """
        params = [dado_normalizado, tipo_validacao]
        
        if exclude_id is not None:
            query_base += " AND id != $3"
            params.append(exclude_id)
        
        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute(query_base, *params)
            logger.info(f"Golden records anteriores desativados para {tipo_validacao}: {dado_normalizado}.")
        except Exception as e:
            logger.error(f"Erro ao desativar golden records antigos para {dado_normalizado} ({tipo_validacao}): {e}", exc_info=True)
            raise

    async def find_duplicate_record(self, dado_original: str, tipo_validacao: str, app_name: str) -> Optional[ValidationRecord]:
        """
        Busca um registro duplicado com base no dado original, tipo de validação e nome do app,
        considerando apenas registros não deletados logicamente.
        """
        query = """
            SELECT * FROM validacoes_gerais
            WHERE dado_original = $1
            AND tipo_validacao = $2
            AND app_name = $3
            AND is_deleted = FALSE;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(query, dado_original, tipo_validacao, app_name)
                if row:
                    logger.info(f"Registro existente encontrado para '{dado_original}' ({tipo_validacao}, {app_name}).")
                    return self._row_to_validation_record(row)
                logger.info(f"Nenhum registro existente encontrado para '{dado_original}' ({tipo_validacao}, {app_name}).")
                return None
        except Exception as e:
            logger.error(f"Erro ao buscar registro duplicado para '{dado_original}' ({tipo_validacao}, {app_name}): {e}", exc_info=True)
            return None

    async def get_last_records(self, limit: int = 10, include_deleted: bool = False) -> List[ValidationRecord]:
        """
        Retorna os últimos N registros de validação, opcionalmente incluindo os deletados.
        """
        if include_deleted:
            query = "SELECT * FROM validacoes_gerais ORDER BY created_at DESC LIMIT $1;"
        else:
            query = "SELECT * FROM validacoes_gerais WHERE is_deleted = FALSE ORDER BY created_at DESC LIMIT $1;"
        
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(query, limit)
                return [self._row_to_validation_record(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao buscar os últimos {limit} registros: {e}", exc_info=True)
            return []

    async def soft_delete_record(self, record_id: int) -> bool:
        """
        Deleta logicamente um registro, marcando 'is_deleted' como TRUE e 'deleted_at' com a data atual.
        `updated_at` é definido pelo trigger no DB.
        """
        query = """
            UPDATE validacoes_gerais
            SET is_deleted = TRUE, deleted_at = $1 -- updated_at é definido pelo trigger
            WHERE id = $2 AND is_deleted = FALSE
            RETURNING id;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                deleted_row_id = await conn.fetchval(query, datetime.now(timezone.utc), record_id)
                if deleted_row_id:
                    logger.info(f"Registro {record_id} marcado como deletado logicamente.")
                    return True
                return False
        except Exception as e:
            logger.error(f"Erro ao tentar soft-delete record {record_id}: {e}", exc_info=True)
            raise

    async def restore_record(self, record_id: int) -> bool:
        """
        Restaura um registro deletado logicamente, marcando 'is_deleted' como FALSE e 'deleted_at' como NULL.
        `updated_at` é definido pelo trigger no DB.
        """
        query = """
            UPDATE validacoes_gerais
            SET is_deleted = FALSE, deleted_at = NULL -- updated_at é definido pelo trigger
            WHERE id = $1 AND is_deleted = TRUE
            RETURNING id;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                restored_row_id = await conn.fetchval(query, record_id)
                if restored_row_id:
                    logger.info(f"Registro {record_id} restaurado com sucesso.")
                    return True
                logger.info(f"Nenhum registro deletado logicamente encontrado com o ID {record_id} para restauração.")
                return False 
        except Exception as e:
            logger.error(f"Erro ao tentar restaurar record {record_id}: {e}", exc_info=True)
            raise