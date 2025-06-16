# app/database/repositories.py
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import asyncpg
import json # Importação necessária para desserialização

from app.database.manager import DatabaseManager
from app.models.validation_record import ValidationRecord # Importa o modelo Pydantic
from pydantic import ValidationError # Importa ValidationError para capturar erros específicos do Pydantic

logger = logging.getLogger(__name__)

class ValidationRecordRepository:
    """
    Repositório para interagir com a tabela 'validacoes_gerais' no banco de dados.
    Gerencia operações CRUD para registros de validação.
    """
    def __init__(self, db_manager: DatabaseManager):
        self.db_pool = db_manager.pool
        if self.db_pool is None:
            raise ValueError("O pool de conexões do DatabaseManager não foi inicializado.")
        logger.info("ValidationRecordRepository inicializado.")

    def _row_to_validation_record(self, row: asyncpg.Record) -> ValidationRecord:
        """
        Converte uma linha (asyncpg.Record) do banco de dados para um modelo ValidationRecord.
        Realiza a desserialização de campos JSONB.
        """
        record_dict = dict(row) # Converte a linha do asyncpg para um dicionário Python

        # Deserializar campos JSONB que Pydantic espera como dicionários
        # asyncpg já pode retornar JSONB como dict, mas é uma boa prática
        # garantir, especialmente se houver inconsistências ou para segurança.
        # No caso de `asyncpg.exceptions.PostgresSyntaxError: INSERT tem mais colunas alvo do que expressões`
        # e o subsequente erro de validação do Pydantic, o asyncpg ESTAVA retornando como string.
        if 'regra_negocio_parametros' in record_dict and isinstance(record_dict['regra_negocio_parametros'], str):
            try:
                record_dict['regra_negocio_parametros'] = json.loads(record_dict['regra_negocio_parametros'])
            except json.JSONDecodeError:
                logger.error(f"Erro ao decodificar JSON para 'regra_negocio_parametros' no record {record_dict.get('id')}: {record_dict['regra_negocio_parametros']}")
                record_dict['regra_negocio_parametros'] = {} # Fallback para dicionário vazio em caso de erro

        if 'validation_details' in record_dict and isinstance(record_dict['validation_details'], str):
            try:
                record_dict['validation_details'] = json.loads(record_dict['validation_details'])
            except json.JSONDecodeError:
                logger.error(f"Erro ao decodificar JSON para 'validation_details' no record {record_dict.get('id')}: {record_dict['validation_details']}")
                record_dict['validation_details'] = {} # Fallback para dicionário vazio em caso de erro
        
        # asyncpg geralmente já retorna datetimes com timezone, mas se necessário,
        # você pode garantir que estejam em UTC, embora não pareça ser a causa do seu problema atual.
        # Exemplo:
        # for key in ['data_validacao', 'created_at', 'updated_at', 'deleted_at']:
        #     if key in record_dict and isinstance(record_dict[key], datetime) and record_dict[key].tzinfo is None:
        #         record_dict[key] = record_dict[key].replace(tzinfo=timezone.utc)

        try:
            # Pydantic 2.x usa model_validate ou model_construct
            # model_validate faz a validação completa, model_construct cria sem validação (mais rápido, mas menos seguro)
            # Para conversão de DB, model_validate é geralmente mais seguro.
            record = ValidationRecord.model_validate(record_dict)
            return record
        except ValidationError as e:
            logger.error(f"Erro ao converter linha do DB para ValidationRecord (erro Pydantic): {e}. Linha: {row}")
            raise # Re-lançar o erro para que a camada superior possa lidar

    async def insert_record(self, data: Dict[str, Any]) -> Optional[ValidationRecord]:
        """
        Insere um novo registro de validação no banco de dados.
        Recebe um dicionário de dados, que deve ter seus campos JSONB já serializados (json.dumps)
        antes de serem passados para este método.
        As colunas com DEFAULT CURRENT_TIMESTAMP (data_validacao, created_at, updated_at)
        e a coluna SERIAL PRIMARY KEY (id) são gerenciadas automaticamente pelo banco e
        NÃO devem ser incluídas no INSERT.
        """
        query = """
            INSERT INTO validacoes_gerais (
                regra_negocio_tipo,      -- $1
                regra_negocio_descricao, -- $2
                regra_negocio_parametros,-- $3 (JSONB como texto)
                usuario_criacao,         -- $4
                usuario_atualizacao,     -- $5
                dado_original,           -- $6
                dado_normalizado,        -- $7
                mensagem,                -- $8
                origem_validacao,        -- $9
                tipo_validacao,          -- $10
                is_valido,               -- $11
                app_name,                -- $12
                client_identifier,       -- $13
                regra_negocio_codigo,    -- $14
                validation_details,      -- $15 (JSONB como texto)
                is_deleted,              -- $16
                deleted_at               -- $17
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
            ) RETURNING *;
        """
        try:
            async with self.db_pool.acquire() as conn:
                inserted_row = await conn.fetchrow(
                    query,
                    data.get('regra_negocio_tipo'),
                    data.get('regra_negocio_descricao'),
                    data.get('regra_negocio_parametros'), # Já deve ser uma string JSON ou None
                    data.get('usuario_criacao'),
                    data.get('usuario_atualizacao'),
                    data.get('dado_original'),
                    data.get('dado_normalizado'),
                    data.get('mensagem'),
                    data.get('origem_validacao'),
                    data.get('tipo_validacao'),
                    data.get('is_valido'),
                    data.get('app_name'),
                    data.get('client_identifier'),
                    data.get('regra_negocio_codigo'),
                    data.get('validation_details'), # Já deve ser uma string JSON ou '{}'
                    data.get('is_deleted'),
                    data.get('deleted_at')
                )
                if inserted_row:
                    logger.info(f"Registro de validação inserido para {data.get('dado_original')}.")
                    return self._row_to_validation_record(inserted_row)
                return None
        except Exception as e:
            logger.error(f"Erro ao inserir registro de validação: {e}", exc_info=True)
            # É importante relançar a exceção para que o serviço que chamou possa tratá-la
            raise

    async def update_record(self, record_id: int, data: Dict[str, Any]) -> Optional[ValidationRecord]:
        """
        Atualiza um registro de validação existente no banco de dados.
        Os campos 'created_at', 'usuario_criacao' e 'id' são excluídos da atualização.
        Recebe um dicionário de dados, que deve ter seus campos JSONB já serializados (json.dumps).
        """
        # Filtra campos que não devem ser atualizados e cria a string SET dinamicamente
        set_parts = []
        values = []
        param_counter = 1
        
        # Campos que podem ser atualizados
        updatable_fields = [
            'regra_negocio_tipo', 'regra_negocio_descricao', 'regra_negocio_parametros',
            'usuario_atualizacao', 'dado_original', 'dado_normalizado', 'mensagem',
            'origem_validacao', 'tipo_validacao', 'is_valido', 'app_name',
            'client_identifier', 'regra_negocio_codigo', 'validation_details',
            'is_deleted', 'deleted_at', 'data_validacao', 'updated_at' # updated_at será sobrescrito pelo trigger
        ]

        # Garantir que updated_at seja sempre atualizado ao chamar este método
        data['updated_at'] = datetime.now(timezone.utc)

        for field in updatable_fields:
            if field in data:
                set_parts.append(f"{field} = ${param_counter}")
                values.append(data[field])
                param_counter += 1

        if not set_parts:
            logger.warning(f"Tentativa de atualizar record {record_id} sem dados válidos para atualização.")
            return None

        # Adiciona o ID ao final dos valores
        values.append(record_id)
        
        query = f"""
            UPDATE validacoes_gerais
            SET {', '.join(set_parts)}
            WHERE id = ${param_counter}
            RETURNING *;
        """
        try:
            async with self.db_pool.acquire() as conn:
                updated_row = await conn.fetchrow(query, *values)
                if updated_row:
                    logger.info(f"Registro de validação {record_id} atualizado com sucesso.")
                    return self._row_to_validation_record(updated_row)
                logger.warning(f"Nenhum registro encontrado com o ID {record_id} para atualização.")
                return None
        except Exception as e:
            logger.error(f"Erro ao atualizar registro de validação {record_id}: {e}", exc_info=True)
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
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(query, dado_original, tipo_validacao, app_name)
                if row:
                    logger.info(f"Registro existente encontrado para '{dado_original}' ({tipo_validacao}, {app_name}).")
                    return self._row_to_validation_record(row)
                logger.info(f"Nenhum registro existente encontrado para '{dado_original}' ({tipo_validacao}, {app_name}).")
                return None
        except Exception as e:
            logger.error(f"Erro ao buscar registro duplicado para '{dado_original}' ({tipo_validacao}, {app_name}): {e}", exc_info=True)
            return None # Retorna None para indicar que a busca falhou

    async def get_last_records(self, limit: int = 10, include_deleted: bool = False) -> List[ValidationRecord]:
        """
        Retorna os últimos N registros de validação, opcionalmente incluindo os deletados.
        """
        if include_deleted:
            query = "SELECT * FROM validacoes_gerais ORDER BY created_at DESC LIMIT $1;"
        else:
            query = "SELECT * FROM validacoes_gerais WHERE is_deleted = FALSE ORDER BY created_at DESC LIMIT $1;"
        
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(query, limit)
                return [self._row_to_validation_record(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao buscar os últimos {limit} registros: {e}", exc_info=True)
            return []

    async def soft_delete_record(self, record_id: int) -> bool:
        """
        Deleta logicamente um registro, marcando 'is_deleted' como TRUE e 'deleted_at' com a data atual.
        """
        query = """
            UPDATE validacoes_gerais
            SET is_deleted = TRUE, deleted_at = $1, updated_at = $1
            WHERE id = $2 AND is_deleted = FALSE
            RETURNING id;
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Usar datetime.now(timezone.utc) para consistência
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
        """
        query = """
            UPDATE validacoes_gerais
            SET is_deleted = FALSE, deleted_at = NULL, updated_at = $1
            WHERE id = $2 AND is_deleted = TRUE
            RETURNING id;
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Usar datetime.now(timezone.utc) para consistência
                restored_row_id = await conn.fetchval(query, datetime.now(timezone.utc), record_id)
                if restored_row_id:
                    logger.info(f"Registro {record_id} restaurado com sucesso.")
                    return True
                return False
        except Exception as e:
            logger.error(f"Erro ao tentar restaurar record {record_id}: {e}", exc_info=True)
            raise