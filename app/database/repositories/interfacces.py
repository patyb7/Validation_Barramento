# app/repositories/interfaces.py (exemplo)
from abc import ABC, abstractmethod
import uuid
from typing import Optional, List
from app.models.client_entity import ClientEntity

class IClientEntityRepository(ABC):
    @abstractmethod
    async def get_by_id(self, entity_id: uuid.UUID) -> Optional[ClientEntity]:
        pass

    @abstractmethod
    async def get_by_document_and_cclub(self, document_normalized: str, cclub: Optional[str]) -> Optional[ClientEntity]:
        pass

    @abstractmethod
    async def save(self, client_entity: ClientEntity) -> ClientEntity:
        pass

    @abstractmethod
    async def delete(self, entity_id: uuid.UUID) -> bool:
        pass