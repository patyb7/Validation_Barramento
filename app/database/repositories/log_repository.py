# app/database/repositories/log_repository.py

import logging
import asyncpg
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
import json # Importar a biblioteca json

# Importe LogEntry do local correto (app.models)
from app.models.log_entry import LogEntry
from app.database.manager import DatabaseManager # Importe DatabaseManager

logger = logging.getLogger(__name__)

class LogRepository:
    """
    Gerencia as operações de persistência para registros de log de auditoria.
    """
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        logger.info("LogRepository inicializado.")

    async def add_log_entry(self, log_entry: LogEntry) -> Optional[LogEntry]:
        """
        Adiciona um novo registro de log de auditoria ao banco de dados.
        """
        if log_entry.id is None:
            log_entry.id = uuid.uuid4()
        if log_entry.timestamp_evento is None: # Usa timestamp_evento
            log_entry.timestamp_evento = datetime.now(timezone.utc)
        if log_entry.created_at is None:
            log_entry.created_at = datetime.now(timezone.utc)

        insert_sql = """
            INSERT INTO audit_logs (
                id, timestamp_evento, tipo_evento, app_origem, usuario_operador,
                record_id_afetado, client_entity_id_afetado, detalhes_evento_json, status_operacao, mensagem_log, created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
            ) RETURNING *;
        """
        params = (
            log_entry.id,
            log_entry.timestamp_evento, # Usa timestamp_evento
            log_entry.tipo_evento,
            log_entry.app_origem,
            log_entry.usuario_operador,
            log_entry.related_record_id,
            log_entry.client_entity_id_afetado, # Novo campo
            json.dumps(log_entry.detalhes_evento_json), # Serializa para JSON string
            log_entry.status_operacao,
            log_entry.mensagem_log,
            log_entry.created_at
        )

        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow(insert_sql, *params)
                if row:
                    row_as_dict = dict(row)
                    # Certifica-se de que JSONB é carregado de volta para dict
                    if isinstance(row_as_dict.get('detalhes_evento_json'), str):
                        row_as_dict['detalhes_evento_json'] = json.loads(row_as_dict['detalhes_evento_json'])
                    
                    # CORRIGIDO: Mapeia timestamp_evento do DB para o campo timestamp_evento do modelo
                    # Renomeia 'timestamp_evento' do DB para 'timestamp_evento' no modelo Pydantic
                    # já que LogEntry espera 'timestamp_evento' (pelo que definimos no modelo)
                    if 'timestamp_evento' in row_as_dict:
                        row_as_dict['timestamp_evento'] = row_as_dict['timestamp_evento']
                    
                    return LogEntry.model_validate(row_as_dict)
                return None
        except Exception as e:
            logger.error(f"Erro inesperado ao adicionar log: {e}", exc_info=True)
            return None

    async def get_all_logs(self, limit: int = 100, app_name: Optional[str] = None, tipo_evento: Optional[str] = None) -> List[LogEntry]:
        """
        Recupera registros de log, com opções de filtro e limite.
        """
        sql = "SELECT * FROM audit_logs WHERE TRUE"
        params: List[Any] = []
        param_counter = 1

        if app_name:
            sql += f" AND app_origem = ${param_counter}"
            params.append(app_name)
            param_counter += 1
        
        if tipo_evento:
            sql += f" AND tipo_evento = ${param_counter}"
            params.append(tipo_evento)
            param_counter += 1

        sql += f" ORDER BY timestamp_evento DESC LIMIT ${param_counter};" # Usa timestamp_evento
        params.append(limit)

        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch(sql, *params)
                processed_logs = []
                for row in rows:
                    row_as_dict = dict(row)
                    if isinstance(row_as_dict.get('detalhes_evento_json'), str):
                        row_as_dict['detalhes_evento_json'] = json.loads(row_as_dict['detalhes_evento_json'])
                    
                    # CORRIGIDO: Mapeia timestamp_evento do DB para o campo timestamp_evento do modelo
                    if 'timestamp_evento' in row_as_dict:
                        row_as_dict['timestamp_evento'] = row_as_dict['timestamp_evento']

                    processed_logs.append(LogEntry.model_validate(row_as_dict))
                return processed_logs
        except Exception as e:
            logger.error(f"Erro ao buscar logs: {e}", exc_info=True)
            return []

