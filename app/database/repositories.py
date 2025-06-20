# app/database/repositories.py
import logging
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
import json
import uuid 
import asyncpg
import re 

from app.models.validation_record import ValidationRecord 

logger = logging.getLogger(__name__)

class ValidationRecordRepository:
    """
    Repositório para interagir com a tabela 'validation_records' no banco de dados,
    gerenciando operações CRUD e consultas específicas.
    """
    def __init__(self, db_manager):
        self.db_manager = db_manager
        logger.info("ValidationRecordRepository inicializado.")

    async def create_record(self, record: ValidationRecord) -> Optional[ValidationRecord]:
        """
        Insere um novo registro de validação no banco de dados.
        O ID é gerado automaticamente pelo banco de dados (UUID DEFAULT gen_random_uuid()).
        """
        insert_sql = """
        INSERT INTO validation_records (
            dado_original, dado_normalizado, is_valido, mensagem,
            origem_validacao, tipo_validacao, app_name, client_identifier,
            validation_details, regra_negocio_codigo, regra_negocio_descricao,
            regra_negocio_tipo, regra_negocio_parametros, usuario_criacao,
            usuario_atualizacao, is_deleted, deleted_at, is_golden_record,
            golden_record_id, status_qualificacao, last_enrichment_attempt_at,
            client_entity_id
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9,
            $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22
        ) RETURNING id, created_at, updated_at, data_validacao;
        """
        try:
            async with self.db_manager.get_connection() as conn: 
                params = [
                    record.dado_original,
                    record.dado_normalizado,
                    record.is_valido,
                    record.mensagem,
                    record.origem_validacao,
                    record.tipo_validacao,
                    record.app_name,
                    record.client_identifier,
                    json.dumps(record.validation_details),
                    record.regra_negocio_codigo,
                    record.regra_negocio_descricao,
                    record.regra_negocio_tipo,
                    json.dumps(record.regra_negocio_parametros) if record.regra_negocio_parametros is not None else None,
                    record.usuario_criacao,
                    record.usuario_atualizacao,
                    record.is_deleted,
                    record.deleted_at,
                    record.is_golden_record,
                    str(record.golden_record_id) if record.golden_record_id else None,
                    record.status_qualificacao,
                    record.last_enrichment_attempt_at,
                    record.client_entity_id
                ]
                
                num_sql_placeholders = len(re.findall(r'\$\d+', insert_sql))
                num_sql_cols_listed = len(insert_sql.split('(')[1].split(')')[0].split(','))

                logger.debug(f"DEBUG REPO create_record: SQL columns listed count: {num_sql_cols_listed}")
                logger.debug(f"DEBUG REPO create_record: SQL placeholders count: {num_sql_placeholders}")
                logger.debug(f"DEBUG REPO create_record: Python parameters count: {len(params)}")
                logger.debug(f"DEBUG REPO create_record: SQL (trimmed): {insert_sql.strip()}")

                row = await conn.fetchrow(insert_sql, *params)
                if row:
                    record.id = row['id']
                    record.created_at = row['created_at']
                    record.updated_at = row['updated_at']
                    record.data_validacao = row['data_validacao']
                    logger.info(f"Registro criado com sucesso. ID: {record.id}")
                    return record
                return None
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao criar registro no banco de dados: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao criar registro: {e}", exc_info=True)
            return None

    async def get_record_by_id(self, record_id: str, include_deleted: bool = False) -> Optional[ValidationRecord]:
        """
        Busca um registro de validação pelo seu ID.
        """
        query_sql = """
        SELECT id, dado_original, dado_normalizado, is_valido, mensagem,
               origem_validacao, tipo_validacao, app_name, client_identifier,
               validation_details, data_validacao,
               regra_negocio_codigo, regra_negocio_descricao,
               regra_negocio_tipo, regra_negocio_parametros,
               usuario_criacao, usuario_atualizacao, is_deleted, deleted_at,
               created_at, updated_at, is_golden_record, golden_record_id,
               status_qualificacao, last_enrichment_attempt_at,
               client_entity_id
        FROM validation_records
        WHERE id = $1
        """
        if not include_deleted:
            query_sql += " AND is_deleted = FALSE"

        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(query_sql, record_id)
                if row:
                    record_data = dict(row)
                    if 'validation_details' in record_data and record_data['validation_details'] is None:
                        record_data['validation_details'] = {}
                    if 'regra_negocio_parametros' in record_data and record_data['regra_negocio_parametros'] is None:
                        record_data['regra_negocio_parametros'] = None

                    for field in ['deleted_at', 'last_enrichment_attempt_at', 'client_entity_id']: 
                        if field in record_data and record_data[field] is None:
                            record_data[field] = None

                    if 'golden_record_id' in record_data and record_data['golden_record_id'] is not None:
                        record_data['golden_record_id'] = str(record_data['golden_record_id'])
                    else:
                        record_data['golden_record_id'] = None
                    
                    if 'id' in record_data and record_data['id'] is not None:
                        record_data['id'] = str(record_data['id'])
                    else:
                        logger.error(f"Registro sem ID ao tentar instanciar ValidationRecord em get_record_by_id: {record_data}")
                        return None 

                    return ValidationRecord(**record_data)
                return None
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao buscar registro {record_id} no banco de dados: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar registro {record_id}: {e}", exc_info=True)
            return None

    async def update_record(self, record_id: str, record: ValidationRecord) -> Optional[ValidationRecord]:
        """
        Atualiza um registro existente no banco de dados.
        """
        update_sql = """
        UPDATE validation_records
        SET dado_original = $1,
            dado_normalizado = $2,
            is_valido = $3,
            mensagem = $4,
            origem_validacao = $5,
            tipo_validacao = $6,
            app_name = $7,
            client_identifier = $8,
            validation_details = $9,
            regra_negocio_codigo = $10,
            regra_negocio_descricao = $11,
            regra_negocio_tipo = $12,
            regra_negocio_parametros = $13,
            usuario_atualizacao = $14,
            is_deleted = $15,
            deleted_at = $16,
            is_golden_record = $17,
            golden_record_id = $18,
            status_qualificacao = $19,
            last_enrichment_attempt_at = $20,
            client_entity_id = $21,
            updated_at = NOW()
        WHERE id = $22
        RETURNING id, updated_at;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(
                    update_sql,
                    record.dado_original,
                    record.dado_normalizado,
                    record.is_valido,
                    record.mensagem,
                    record.origem_validacao,
                    record.tipo_validacao,
                    record.app_name,
                    record.client_identifier,
                    json.dumps(record.validation_details),
                    record.regra_negocio_codigo,
                    record.regra_negocio_descricao,
                    record.regra_negocio_tipo,
                    json.dumps(record.regra_negocio_parametros) if record.regra_negocio_parametros is not None else None,
                    record.usuario_atualizacao,
                    record.is_deleted,
                    record.deleted_at,
                    record.is_golden_record,
                    str(record.golden_record_id) if record.golden_record_id else None,
                    record.status_qualificacao,
                    record.last_enrichment_attempt_at,
                    record.client_entity_id,
                    record_id 
                )
                if row:
                    record.id = row['id']
                    record.updated_at = row['updated_at']
                    logger.info(f"Registro atualizado com sucesso. ID: {record.id}")
                    return record
                return None
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao atualizar registro {record_id} no banco de dados: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao atualizar registro {record_id}: {e}", exc_info=True)
            return None

    async def soft_delete_record(self, record_id: str) -> bool:
        """
        Executa um soft delete (exclusão lógica) de um registro.
        Define 'is_deleted' como TRUE e 'deleted_at' com o timestamp atual.
        """
        update_sql = """
        UPDATE validation_records
        SET is_deleted = TRUE,
            deleted_at = NOW(),
            updated_at = NOW()
        WHERE id = $1 AND is_deleted = FALSE
        RETURNING id;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(update_sql, record_id)
                if row:
                    logger.info(f"Registro {record_id} soft-deletado com sucesso.")
                    return True
                logger.warning(f"Registro {record_id} não encontrado ou já soft-deletado.")
                return False 
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao soft-deletar registro {record_id}: {e}", exc_info=True)
            return False 
        except Exception as e:
            logger.error(f"Erro inesperado ao soft-deletar registro {record_id}: {e}", exc_info=True)
            return False

    async def restore_record(self, record_id: str) -> bool:
        """
        Restaura um registro que foi soft-deletado (define 'is_deleted' como FALSE e 'deleted_at' como NULL).
        """
        update_sql = """
        UPDATE validation_records
        SET is_deleted = FALSE,
            deleted_at = NULL,
            updated_at = NOW()
        WHERE id = $1 AND is_deleted = TRUE
        RETURNING id;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(update_sql, record_id)
                if row:
                    logger.info(f"Registro {record_id} restaurado com sucesso.")
                    return True
                logger.warning(f"Registro {record_id} não encontrado ou não estava soft-deletado.")
                return False
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao restaurar registro {record_id}: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao restaurar registro {record_id}: {e}", exc_info=True)
            return False

    async def get_last_records(self, limit: int = 10, include_deleted: bool = False) -> List[ValidationRecord]:
        """
        Retorna os últimos N registros de validação, opcionalmente incluindo os deletados.
        """
        query_sql = """
        SELECT id, dado_original, dado_normalizado, is_valido, mensagem,
               origem_validacao, tipo_validacao, app_name, client_identifier,
               validation_details, data_validacao,
               regra_negocio_codigo, regra_negocio_descricao,
               regra_negocio_tipo, regra_negocio_parametros,
               usuario_criacao, usuario_atualizacao, is_deleted, deleted_at,
               created_at, updated_at, is_golden_record, golden_record_id,
               status_qualificacao, last_enrichment_attempt_at,
               client_entity_id
        FROM validation_records
        """
        conditions = []
        if not include_deleted:
            conditions.append("is_deleted = FALSE")
        
        if conditions:
            query_sql += " WHERE " + " AND ".join(conditions)

        query_sql += " ORDER BY data_validacao DESC, id DESC LIMIT $1;"

        records: List[ValidationRecord] = []
        try:
            logger.debug(f"Executando query para get_last_records: {query_sql.strip()} com limite {limit}")
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(query_sql, limit)
                logger.debug(f"Retornadas {len(rows)} linhas do banco de dados para histórico.")
                for row in rows:
                    record_data = dict(row)
                    record_id = record_data.get('id', 'N/A')
                    logger.debug(f"Processando registro ID: {record_id}")

                    if 'validation_details' in record_data and record_data['validation_details'] is None:
                        record_data['validation_details'] = {}
                    if 'regra_negocio_parametros' in record_data and record_data['regra_negocio_parametros'] is None:
                        record_data['regra_negocio_parametros'] = None
                    
                    for field in ['deleted_at', 'last_enrichment_attempt_at']:
                        if field in record_data and record_data[field] is None:
                            record_data[field] = None
                    
                    if 'golden_record_id' in record_data and record_data['golden_record_id'] is not None:
                        record_data['golden_record_id'] = str(record_data['golden_record_id'])
                    else:
                        record_data['golden_record_id'] = None
                    
                    if 'id' in record_data and record_data['id'] is not None:
                        record_data['id'] = str(record_data['id'])
                    else:
                        logger.error(f"Registro sem ID ao tentar instanciar ValidationRecord: {record_data}")
                        continue

                    try:
                        record_instance = ValidationRecord(**record_data)
                        records.append(record_instance)
                        logger.debug(f"Registro ID {record_id} adicionado à lista de histórico.")
                    except Exception as pydantic_e:
                        logger.error(f"Erro ao instanciar ValidationRecord para registro ID {record_id}: {pydantic_e}. Dados: {record_data}", exc_info=True)
                        pass 

            logger.info(f"Recuperados {len(records)} registros do histórico (limite: {limit}, deletados: {include_deleted}).")
            return records
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao buscar últimos registros no banco de dados: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar últimos registros: {e}", exc_info=True)
            return []

    async def get_all_records_by_normalized_data(self, dado_normalizado: str, tipo_validacao: str, include_deleted: bool = False) -> List[ValidationRecord]:
        """
        Busca todos os registros associados a um dado normalizado e tipo de validação específicos.
        Útil para a lógica de Golden Record.
        """
        query_sql = """
        SELECT id, dado_original, dado_normalizado, is_valido, mensagem,
               origem_validacao, tipo_validacao, app_name, client_identifier,
               validation_details, data_validacao,
               regra_negocio_codigo, regra_negocio_descricao,
               regra_negocio_tipo, regra_negocio_parametros,
               usuario_criacao, usuario_atualizacao, is_deleted, deleted_at,
               created_at, updated_at, is_golden_record, golden_record_id,
               status_qualificacao, last_enrichment_attempt_at,
               client_entity_id
        FROM validation_records
        WHERE dado_normalizado = $1 AND tipo_validacao = $2
        """
        if not include_deleted:
            query_sql += " AND is_deleted = FALSE"
        
        records: List[ValidationRecord] = []
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(query_sql, dado_normalizado, tipo_validacao)
                for row in rows:
                    record_data = dict(row)
                    if 'validation_details' in record_data and record_data['validation_details'] is None:
                        record_data['validation_details'] = {}
                    if 'regra_negocio_parametros' in record_data and record_data['regra_negocio_parametros'] is None:
                        record_data['regra_negocio_parametros'] = None

                    for field in ['deleted_at', 'last_enrichment_attempt_at']:
                        if field in record_data and record_data[field] is None:
                            record_data[field] = None
                    
                    if 'golden_record_id' in record_data and record_data['golden_record_id'] is not None:
                        record_data['golden_record_id'] = str(record_data['golden_record_id'])
                    else:
                        record_data['golden_record_id'] = None
                    
                    if 'id' in record_data and record_data['id'] is not None:
                        record_data['id'] = str(record_data['id'])
                    else:
                        logger.error(f"Registro sem ID ao tentar instanciar ValidationRecord: {record_data}")
                        continue

                    records.append(ValidationRecord(**record_data))
            logger.info(f"Recuperados {len(records)} registros para '{dado_normalizado}' ({tipo_validacao}).")
            return records
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao buscar registros por dado normalizado '{dado_normalizado}': {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar registros por dado normalizado '{dado_normalizado}': {e}", exc_info=True)
            return []

    async def update_golden_record_status(self, record_id: str, is_golden: bool, golden_record_id: Optional[str]) -> bool:
        """
        Atualiza o status de Golden Record para um registro específico.
        """
        update_sql = """
        UPDATE validation_records
        SET is_golden_record = $1,
            golden_record_id = $2,
            updated_at = NOW()
        WHERE id = $3
        RETURNING id;
        """
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(update_sql, is_golden, golden_record_id, record_id)
                if row:
                    logger.debug(f"Status GR do registro {record_id} atualizado para is_golden_record={is_golden}, golden_record_id={golden_record_id}.")
                    return True
                logger.warning(f"Registro {record_id} não encontrado para atualizar status GR.")
                return False
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao atualizar status GR do registro {record_id}: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao atualizar status GR do registro {record_id}: {e}", exc_info=True)
            return False

    async def find_duplicate_record(self, dado_normalizado: str, tipo_validacao: str, app_name: str, client_identifier: Optional[str] = None, exclude_record_id: Optional[str] = None) -> Optional[ValidationRecord]:
        """
        Busca um registro duplicado baseado em dado normalizado, tipo de validação e nome da aplicação.
        Exclui registros logicamente deletados e, opcionalmente, um ID de registro específico.
        """
        query_sql = """
        SELECT id, dado_original, dado_normalizado, is_valido, mensagem,
               origem_validacao, tipo_validacao, app_name, client_identifier,
               validation_details, data_validacao,
               regra_negocio_codigo, regra_negocio_descricao,
               regra_negocio_tipo, regra_negocio_parametros,
               usuario_criacao, usuario_atualizacao, is_deleted, deleted_at,
               created_at, updated_at, is_golden_record, golden_record_id,
               status_qualificacao, last_enrichment_attempt_at,
               client_entity_id
        FROM validation_records
        WHERE dado_normalizado = $1
          AND tipo_validacao = $2
          AND app_name = $3
          AND is_deleted = FALSE
        """
        params = [dado_normalizado, tipo_validacao, app_name]
        param_idx = 4 

        if client_identifier is not None:
            query_sql += f" AND client_identifier = ${param_idx}"
            params.append(client_identifier)
            param_idx += 1
        else: 
             query_sql += f" AND (client_identifier IS NULL OR client_identifier = '')"


        if exclude_record_id is not None:
            query_sql += f" AND id != ${param_idx}"
            params.append(exclude_record_id)
            param_idx += 1

        query_sql += " LIMIT 1;"

        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(query_sql, *params)
                if row:
                    record_data = dict(row)
                    if 'validation_details' in record_data and record_data['validation_details'] is None:
                        record_data['validation_details'] = {}
                    if 'regra_negocio_parametros' in record_data and record_data['regra_negocio_parametros'] is None:
                        record_data['regra_negocio_parametros'] = None
                    
                    for field in ['deleted_at', 'last_enrichment_attempt_at']:
                        if field in record_data and record_data[field] is None:
                            record_data[field] = None
                    
                    if 'golden_record_id' in record_data and record_data['golden_record_id'] is not None:
                        record_data['golden_record_id'] = str(record_data['golden_record_id'])
                    else:
                        record_data['golden_record_id'] = None
                    
                    if 'id' in record_data and record_data['id'] is not None:
                        record_data['id'] = str(record_data['id'])
                    else:
                        logger.error(f"Registro sem ID ao tentar instanciar ValidationRecord: {record_data}")
                        return None 

                    logger.info(f"Duplicidade encontrada para '{dado_normalizado}' (Tipo: {tipo_validacao}, App: {app_name}). ID: {row['id']}")
                    return ValidationRecord(**record_data)
                logger.debug(f"Nenhuma duplicidade encontrada para '{dado_normalizado}' (Tipo: {tipo_validacao}, App: {app_name}).")
                return None
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao buscar duplicidade para '{dado_normalizado}': {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar duplicidade para '{dado_normalizado}': {e}", exc_info=True)
            return None

    async def get_records_by_golden_record_id(self, golden_record_id: str, include_deleted: bool = False) -> List[ValidationRecord]:
        """
        Busca todos os registros associados a um Golden Record específico.
        Útil para recuperar todos os registros que compõem um Golden Record.
        """
        query_sql = """
        SELECT id, dado_original, dado_normalizado, is_valido, mensagem,
               origem_validacao, tipo_validacao, app_name, client_identifier,
               validation_details, data_validacao,
               regra_negocio_codigo, regra_negocio_descricao,
               regra_negocio_tipo, regra_negocio_parametros,
               usuario_criacao, usuario_atualizacao, is_deleted, deleted_at,
               created_at, updated_at, is_golden_record, golden_record_id,
               status_qualificacao, last_enrichment_attempt_at,
               client_entity_id
        FROM validation_records
        WHERE golden_record_id = $1
        """
        if not include_deleted:
            query_sql += " AND is_deleted = FALSE"

        records: List[ValidationRecord] = []
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(query_sql, golden_record_id)
                for row in rows:
                    record_data = dict(row)
                    if 'validation_details' in record_data and record_data['validation_details'] is None:
                        record_data['validation_details'] = {}
                    if 'regra_negocio_parametros' in record_data and record_data['regra_negocio_parametros'] is None:
                        record_data['regra_negocio_parametros'] = None

                    for field in ['deleted_at', 'last_enrichment_attempt_at']:
                        if field in record_data and record_data[field] is None:
                            record_data[field] = None
                    
                    if 'golden_record_id' in record_data and record_data['golden_record_id'] is not None:
                        record_data['golden_record_id'] = str(record_data['golden_record_id'])
                    else:
                        record_data['golden_record_id'] = None
                    
                    if 'id' in record_data and record_data['id'] is not None:
                        record_data['id'] = str(record_data['id'])
                    else:
                        logger.error(f"Registro sem ID ao tentar instanciar ValidationRecord: {record_data}")
                        continue

                    records.append(ValidationRecord(**record_data))
            logger.info(f"Recuperados {len(records)} registros para Golden Record ID '{golden_record_id}'.")
            return records
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao buscar registros por Golden Record ID '{golden_record_id}': {e}", exc_info=True)
            return [] 
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar registros por Golden Record ID '{golden_record_id}': {e}", exc_info=True)
            return []

    async def get_records_by_client_entity_id(self, client_entity_id: str, include_deleted: bool = False) -> List[ValidationRecord]:
        """
        Busca todos os registros associados a um ID de entidade cliente específico.
        Útil para recuperar todos os registros relacionados a uma entidade cliente.
        """
        query_sql = """
        SELECT id, dado_original, dado_normalizado, is_valido, mensagem,
               origem_validacao, tipo_validacao, app_name, client_identifier,
               validation_details, data_validacao,
               regra_negocio_codigo, regra_negocio_descricao,
               regra_negocio_tipo, regra_negocio_parametros,
               usuario_criacao, usuario_atualizacao, is_deleted, deleted_at,
               created_at, updated_at, is_golden_record, golden_record_id,
               status_qualificacao, last_enrichment_attempt_at,
               client_entity_id
        FROM validation_records
        WHERE client_entity_id = $1
        """
        if not include_deleted:
            query_sql += " AND is_deleted = FALSE"

        records: List[ValidationRecord] = []
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(query_sql, client_entity_id)
                for row in rows:
                    record_data = dict(row)
                    if 'validation_details' in record_data and record_data['validation_details'] is None:
                        record_data['validation_details'] = {}
                    if 'regra_negocio_parametros' in record_data and record_data['regra_negocio_parametros'] is None:
                        record_data['regra_negocio_parametros'] = None

                    for field in ['deleted_at', 'last_enrichment_attempt_at']:
                        if field in record_data and record_data[field] is None:
                            record_data[field] = None
                    
                    if 'golden_record_id' in record_data and record_data['golden_record_id'] is not None:
                        record_data['golden_record_id'] = str(record_data['golden_record_id'])
                    else:
                        record_data['golden_record_id'] = None
                    
                    if 'id' in record_data and record_data['id'] is not None:
                        record_data['id'] = str(record_data['id'])
                    else:
                        logger.error(f"Registro sem ID ao tentar instanciar ValidationRecord: {record_data}")
                        continue

                    records.append(ValidationRecord(**record_data))
            logger.info(f"Recuperados {len(records)} registros para Client Entity ID '{client_entity_id}'.")
            return records
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao buscar registros por Client Entity ID '{client_entity_id}': {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar registros por Client Entity ID '{client_entity_id}': {e}", exc_info=True)
            return []

    async def get_records_by_app_name(self, app_name: str, include_deleted: bool = False) -> List[ValidationRecord]:
        """
        Busca todos os registros associados a um nome de aplicação específico.
        Útil para recuperar todos os registros relacionados a uma aplicação.
        """
        query_sql = """
        SELECT id, dado_original, dado_normalizado, is_valido, mensagem,
               origem_validacao, tipo_validacao, app_name, client_identifier,
               validation_details, data_validacao,
               regra_negocio_codigo, regra_negocio_descricao,
               regra_negocio_tipo, regra_negocio_parametros,
               usuario_criacao, usuario_atualizacao, is_deleted, deleted_at,
               created_at, updated_at, is_golden_record, golden_record_id,
               status_qualificacao, last_enrichment_attempt_at,
               client_entity_id
        FROM validation_records
        WHERE app_name = $1
        """
        if not include_deleted:
            query_sql += " AND is_deleted = FALSE"
        
        records: List[ValidationRecord] = []
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(query_sql, app_name)
                for row in rows:
                    record_data = dict(row)
                    if 'validation_details' in record_data and record_data['validation_details'] is None:
                        record_data['validation_details'] = {}
                    if 'regra_negocio_parametros' in record_data and record_data['regra_negocio_parametros'] is None:
                        record_data['regra_negocio_parametros'] = None

                    for field in ['deleted_at', 'last_enrichment_attempt_at']:
                        if field in record_data and record_data[field] is None:
                            record_data[field] = None
                    
                    if 'golden_record_id' in record_data and record_data['golden_record_id'] is not None:
                        record_data['golden_record_id'] = str(record_data['golden_record_id'])
                    else:
                        record_data['golden_record_id'] = None
                    
                    if 'id' in record_data and record_data['id'] is not None:
                        record_data['id'] = str(record_data['id'])
                    else:
                        logger.error(f"Registro sem ID ao tentar instanciar ValidationRecord: {record_data}")
                        continue

                    records.append(ValidationRecord(**record_data))
            logger.info(f"Recuperados {len(records)} registros para a aplicação '{app_name}'.")
            return records
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Erro ao buscar registros por nome da aplicação '{app_name}': {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar registros por nome da aplicação '{app_name}': {e}", exc_info=True)
            return []
