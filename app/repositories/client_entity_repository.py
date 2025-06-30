# repositories/client_entity_repository.py

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import uuid

from app.models.client_entity import ClientEntity

logger = logging.getLogger(__name__)

class ClientEntityRepository:
    """
    Repositório em memória para a gestão de entidades de cliente (ClientEntity).
    Em um ambiente de produção, esta classe seria implementada para interagir
    com um banco de dados persistente (ex: PostgreSQL com asyncpg).
    """
    def __init__(self):
        # Simula um banco de dados em memória para ClientEntity
        self._client_entities: Dict[str, ClientEntity] = {} 
        logger.info("ClientEntityRepository inicializado (em memória).")

    async def get_by_id(self, entity_id: str) -> Optional[ClientEntity]:
        """Busca uma ClientEntity pelo seu ID."""
        logger.debug(f"Buscando ClientEntity pelo ID: {entity_id}")
        return self._client_entities.get(entity_id)

    async def get_by_document_and_cclub(self, document_normalized: str, cclub: Optional[str]) -> Optional[ClientEntity]:
        """
        Busca uma ClientEntity pelo CPF/CNPJ principal normalizado e CCLUB.
        Esta seria a lógica principal para identificar um cliente existente no contexto do barramento.
        """
        logger.debug(f"Buscando ClientEntity por documento '{document_normalized}' e CCLUB '{cclub}'")
        for entity in self._client_entities.values():
            if entity.main_document_normalized == document_normalized and (entity.cclub == cclub or (entity.cclub is None and cclub is None)):
                return entity
        return None

    async def save(self, client_entity: ClientEntity) -> ClientEntity:
        """Salva ou atualiza uma ClientEntity."""
        logger.debug(f"Salvando/Atualizando ClientEntity com ID: {client_entity.id}")
        
        # Garante que created_at seja definido apenas na criação (em memória)
        # Em um DB real, o default da coluna cuida disso.
        if client_entity.id not in self._client_entities:
            client_entity.created_at = datetime.now(timezone.utc)
        
        # Sempre atualiza o updated_at no repositório (em um DB real, um trigger faria isso)
        client_entity.updated_at = datetime.now(timezone.utc) 
        
        # Em um DB real, aqui você teria uma operação upsert (insert or update)
        self._client_entities[client_entity.id] = client_entity
        
        return client_entity

    async def delete(self, entity_id: str):
        """Deleta uma ClientEntity pelo seu ID."""
        logger.debug(f"Deletando ClientEntity com ID: {entity_id}")
        if entity_id in self._client_entities:
            del self._client_entities[entity_id]
            logger.info(f"ClientEntity {entity_id} deletada com sucesso.")
            return True
        logger.warning(f"Tentativa de deletar ClientEntity inexistente: {entity_id}")
        return False