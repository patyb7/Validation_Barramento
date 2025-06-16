# app/database/repositories.py

import json
from typing import List, Optional
from datetime import datetime
import logging

from app.database.manager import DatabaseManager
from app.models.validation_record import ValidationRecord

logger = logging.getLogger(__name__)

class ValidationRecordRepository:
    """
    Repositório para operações CRUD (Create, Read, Update, Delete Lógico)
    relacionadas aos registros de validação na tabela 'validacoes_telefone' (ou 'validacoes_gerais' se for mais abrangente).
    """
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def _map_row_to_record(self, row) -> ValidationRecord:
        """
        Função auxiliar para mapear uma linha do banco de dados (tupla)
        para um objeto ValidationRecord.
        A ordem dos índices deve corresponder à ordem das colunas no SELECT.
        """
        if not row:
            return None

        # Ajustado para os novos nomes de campo e a ordem esperada do SELECT
        return ValidationRecord(
            id=row[0],
            dado_original=row[1],     # Renomeado
            dado_normalizado=row[2],  # Renomeado
            valido=row[3],
            mensagem=row[4],
            origem_validacao=row[5],
            tipo_validacao=row[6],
            data_validacao=row[7], 
            app_name=row[8],
            client_identifier=row[9],
            regra_codigo=row[10],
            validation_details=row[11],
            is_deleted=row[12],
            deleted_at=row[13]
        )

    def insert_record(self, record: ValidationRecord) -> int:
        """
        Insere um novo registro de validação no banco de dados.
        O ID do registro é atualizado no objeto 'record' após a inserção.
        Retorna o ID do registro inserido.
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            # ATENÇÃO: O nome da tabela 'validacoes_telefone' ainda é específico.
            # Se o serviço for "universal", talvez você queira mudar o nome da tabela no DB
            # para algo como 'validacoes_gerais' ou 'validation_records' e atualizar aqui.
            cursor.execute(
                """
                INSERT INTO validacoes_telefone (
                    dado_original, dado_normalizado, valido, mensagem,
                    origem_validacao, tipo_validacao, data_validacao, app_name,
                    client_identifier, regra_codigo, validation_details,
                    is_deleted, deleted_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    record.dado_original,      # Renomeado
                    record.dado_normalizado,   # Renomeado
                    record.valido,
                    record.mensagem,
                    record.origem_validacao,
                    record.tipo_validacao,
                    record.data_validacao, 
                    record.app_name,
                    record.client_identifier,
                    record.regra_codigo,
                    json.dumps(record.validation_details), # Converte o dicionário para JSON string
                    record.is_deleted,
                    record.deleted_at
                )
            )
            record.id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Registro de validação inserido com ID: {record.id}")
            return record.id
        except Exception as e:
            logger.error(f"ERRO: Falha ao inserir registro de validação: {e}", exc_info=True)
            if conn:
                conn.rollback() 
            raise
        finally:
            if conn:
                self.db_manager.return_connection(conn)

    def _get_base_select_query(self) -> str:
        """Retorna a parte SELECT base da query para evitar repetição.
        Deve incluir os campos renomeados e 'tipo_validacao' na ordem correta.
        """
        # ATENÇÃO: O nome da tabela 'validacoes_telefone' ainda é específico aqui também.
        return """
            SELECT
                id, dado_original, dado_normalizado, valido, mensagem,
                origem_validacao, tipo_validacao, data_validacao, app_name,
                client_identifier, regra_codigo, validation_details,
                is_deleted, deleted_at
            FROM validacoes_telefone
        """

    def get_last_records(self, limit: int = 5, include_deleted: bool = False) -> List[ValidationRecord]:
        conn = None
        records = []
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            query = self._get_base_select_query()
            params = []

            if not include_deleted:
                query += " WHERE is_deleted = FALSE"
            
            query += " ORDER BY data_validacao DESC LIMIT %s;"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            for row in rows:
                records.append(self._map_row_to_record(row))
        except Exception as e:
            logger.error(f"ERRO: Falha ao buscar últimos registros de validação: {e}", exc_info=True)
            raise
        finally:
            if conn:
                self.db_manager.return_connection(conn)
        return records

    def get_record_by_id(self, record_id: int, include_deleted: bool = False) -> Optional[ValidationRecord]:
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            query = self._get_base_select_query()
            query += " WHERE id = %s"
            params = [record_id]

            if not include_deleted:
                query += " AND is_deleted = FALSE"
            query += ";"

            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            return self._map_row_to_record(row)
        except Exception as e:
            logger.error(f"ERRO: Falha ao buscar registro por ID {record_id}: {e}", exc_info=True)
            raise
        finally:
            if conn:
                self.db_manager.return_connection(conn)

    def get_records_by_client_identifier(self, client_id: str, limit: int = 10, include_deleted: bool = False) -> List[ValidationRecord]:
        conn = None
        records = []
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            query = self._get_base_select_query()
            query += " WHERE client_identifier = %s"
            params = [client_id]

            if not include_deleted:
                query += " AND is_deleted = FALSE"
            
            query += " ORDER BY data_validacao DESC LIMIT %s;"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            for row in rows:
                records.append(self._map_row_to_record(row))
        except Exception as e:
            logger.error(f"ERRO: Falha ao buscar registros para cliente '{client_id}': {e}", exc_info=True)
            raise
        finally:
            if conn:
                self.db_manager.return_connection(conn)
            return records

    def soft_delete_record_by_id(self, record_id: int) -> bool:
        """
        Realiza uma exclusão lógica (soft delete) de um registro,
        marcando 'is_deleted' como TRUE e preenchendo 'deleted_at'.
        Retorna True se o registro foi encontrado e deletado, False caso contrário.
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE validacoes_telefone
                SET is_deleted = TRUE, deleted_at = %s
                WHERE id = %s;
                """,
                (datetime.now(), record_id)
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Registro com ID {record_id} marcado como deletado (soft delete).")
                return True
            else:
                logger.warning(f"Tentativa de soft delete para ID {record_id}, mas registro não encontrado ou já deletado.")
                return False
        except Exception as e:
            logger.error(f"ERRO: Falha ao soft delete o registro com ID {record_id}: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.db_manager.return_connection(conn)

    def restore_record(self, record_id: int) -> bool:
        """
        Restaura um registro que foi soft deletado,
        definindo 'is_deleted' como FALSE e 'deleted_at' como NULL.
        Retorna True se o registro foi encontrado e restaurado, False caso contrário.
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE validacoes_telefone
                SET is_deleted = FALSE, deleted_at = NULL
                WHERE id = %s;
                """,
                (record_id,)
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Registro com ID {record_id} restaurado (soft delete revertido).")
                return True
            else:
                logger.warning(f"Tentativa de restauração para ID {record_id}, mas registro não encontrado ou não deletado.")
                return False
        except Exception as e:
            logger.error(f"ERRO: Falha ao restaurar o registro com ID {record_id}: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.db_manager.return_connection(conn)

    def hard_delete_record(self, record_id: int) -> bool:
        """
        **ATENÇÃO: Exclui fisicamente um registro do banco de dados.**
        Use com extrema cautela, geralmente apenas em ambientes de desenvolvimento
        ou para limpeza de dados específicos e críticos (ex: dados muito sensíveis).
        Retorna True se o registro foi encontrado e deletado, False caso contrário.
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM validacoes_telefone WHERE id = %s;",
                (record_id,)
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.warning(f"Registro com ID {record_id} EXCLUÍDO FISICAMENTE do banco de dados.")
                return True
            else:
                logger.warning(f"Tentativa de hard delete para ID {record_id}, mas registro não encontrado.")
                return False
        except Exception as e:
            logger.error(f"ERRO: Falha ao EXCLUIR FISICAMENTE o registro com ID {record_id}: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.db_manager.return_connection(conn)
    
    def find_duplicate_record(self, dado_normalizado: str, tipo_validacao: str, exclude_record_id: Optional[int] = None) -> Optional[ValidationRecord]:
        """
        Busca por um registro de validação duplicado (mesmo dado normalizado e tipo de validação).
        Pode excluir um ID de registro específico da busca para evitar que o próprio registro
        recém-inserido seja considerado duplicado.
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            query = self._get_base_select_query()
            query += " WHERE dado_normalizado = %s AND tipo_validacao = %s" # Renomeado
            params = [dado_normalizado, tipo_validacao] # Renomeado

            if exclude_record_id is not None:
                query += " AND id != %s"
                params.append(exclude_record_id)
            
            # Adiciona uma cláusula para não considerar registros soft-deletados como duplicatas "ativas"
            query += " AND is_deleted = FALSE"
            
            query += " LIMIT 1;" # Apenas o primeiro duplicado é suficiente

            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            return self._map_row_to_record(row)
        except Exception as e:
            logger.error(f"ERRO: Falha ao buscar registro duplicado para '{dado_normalizado}' ({tipo_validacao}): {e}", exc_info=True)
            raise
        finally:
            if conn:
                self.db_manager.return_connection(conn)