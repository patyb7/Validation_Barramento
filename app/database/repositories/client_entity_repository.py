import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import uuid # Importar uuid para usar UUIDs (ClientEntity.id é UUID)

from app.models.client_entity import ClientEntity # Importa o modelo Pydantic ClientEntity

logger = logging.getLogger(__name__)

class ClientEntityRepository:
    """
    Repositório em memória para a gestão de entidades de cliente (ClientEntity).
    Esta classe simula o comportamento de um banco de dados persistente
    para fins de teste e demonstração.
    """
    def __init__(self):
        # Simula um banco de dados em memória para ClientEntity, usando o ID UUID da entidade como chave
        self._client_entities: Dict[str, ClientEntity] = {} 
        logger.info("ClientEntityRepository inicializado (em memória).")

    async def get_by_id(self, entity_id: uuid.UUID) -> Optional[ClientEntity]: # Tipado como uuid.UUID
        """Busca uma ClientEntity pelo seu ID (UUID)."""
        logger.debug(f"Buscando ClientEntity pelo ID: {entity_id}")
        # Converte o UUID para string para buscar no dicionário
        return self._client_entities.get(str(entity_id))

    async def get_by_document_and_cclub(self, document_normalized: str, cclub: Optional[str]) -> Optional[ClientEntity]:
        """
        Busca uma ClientEntity pelo CPF/CNPJ principal normalizado e CCLUB em memória.
        Esta seria a lógica principal para identificar um cliente existente no contexto do barramento.
        """
        logger.debug(f"Buscando ClientEntity por documento '{document_normalized}' e CCLUB '{cclub}'")
        for entity in self._client_entities.values():
            if entity.main_document_normalized == document_normalized and (entity.cclub == cclub or (entity.cclub is None and cclub is None)):
                return entity
        return None

    async def save(self, client_entity: ClientEntity) -> ClientEntity:
        """Salva ou atualiza uma ClientEntity em memória."""
        logger.debug(f"Salvando/Atualizando ClientEntity com ID: {client_entity.id}")
        
        # Garante que created_at seja definido apenas na criação (em memória)
        # Em um DB real, o default da coluna cuida disso.
        if str(client_entity.id) not in self._client_entities: # Usa str(client_entity.id) para verificar no dicionário
            client_entity.created_at = datetime.now(timezone.utc)
        
        # Sempre atualiza o updated_at no repositório (em um DB real, um trigger faria isso)
        client_entity.updated_at = datetime.now(timezone.utc) 
        
        # Em um DB real, aqui você teria uma operação upsert (insert or update)
        self._client_entities[str(client_entity.id)] = client_entity # Usa str(client_entity.id) como chave
        
        return client_entity

    async def delete(self, entity_id: uuid.UUID) -> bool: # Tipado como uuid.UUID
        """Deleta uma ClientEntity pelo seu ID (UUID) em memória."""
        logger.debug(f"Deletando ClientEntity com ID: {entity_id}")
        entity_id_str = str(entity_id) # Converte para string para buscar no dicionário
        if entity_id_str in self._client_entities:
            del self._client_entities[entity_id_str]
            logger.info(f"ClientEntity {entity_id} deletada em memória com sucesso.")
            return True
        logger.warning(f"Tentativa de deletar ClientEntity inexistente em memória: {entity_id}")
        return False
    async def list_all(self) -> List[ClientEntity]:
        """Lista todas as ClientEntities armazenadas em memória."""
        logger.debug("Listando todas as ClientEntities em memória.")
        return list(self._client_entities.values()) # Retorna uma lista de ClientEntity, não um dicionário