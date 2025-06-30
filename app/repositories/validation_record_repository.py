# repositories/validation_record_repository.py

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.models.validation_record import ValidationRecord # Assumindo que ValidationRecord é um modelo Pydantic

logger = logging.getLogger(__name__)

class ValidationRecordRepository:
    def __init__(self):
        # Simula um banco de dados em memória para ValidationRecord
        self._records: Dict[int, ValidationRecord] = {}
        self._next_id = 1
        logger.info("ValidationRecordRepository inicializado (em memória).")

    async def create_record(self, record: ValidationRecord) -> Optional[ValidationRecord]:
        record.id = self._next_id
        self._next_id += 1
        record.created_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)
        self._records[record.id] = record
        logger.debug(f"Registro criado: {record.id}")
        return record

    async def get_record_by_id(self, record_id: int) -> Optional[ValidationRecord]:
        logger.debug(f"Buscando registro por ID: {record_id}")
        return self._records.get(record_id)

    async def update_record(self, record_id: int, updated_record: ValidationRecord) -> Optional[ValidationRecord]:
        if record_id not in self._records:
            logger.warning(f"Tentativa de atualizar registro inexistente: {record_id}")
            return None
        
        current_record = self._records[record_id]
        
        # Atualiza os campos do registro existente com os valores do updated_record
        # Usamos model_dump para obter um dict dos campos do Pydantic, excluindo o ID e timestamps de criação
        update_data = updated_record.model_dump(exclude_unset=True, exclude={'id', 'created_at'})
        for field, value in update_data.items():
            setattr(current_record, field, value)
            
        current_record.updated_at = datetime.now(timezone.utc) # Atualiza explicitamente o updated_at
        
        logger.debug(f"Registro atualizado: {record_id}")
        return current_record

    async def get_all_records_by_normalized_data(self, dado_normalizado: str, tipo_validacao: str) -> List[ValidationRecord]:
        """Retorna todos os registros não-deletados para um dado normalizado e tipo de validação."""
        logger.debug(f"Buscando todos os registros para dado_normalizado='{dado_normalizado}' e tipo_validacao='{tipo_validacao}'")
        return [
            rec for rec in self._records.values()
            if rec.dado_normalizado == dado_normalizado and
               rec.tipo_validacao == tipo_validacao and
               not rec.is_deleted
        ]

    async def set_golden_record_false_for_normalized_data(self, dado_normalizado: str, tipo_validacao: str, exclude_id: Optional[int] = None):
        """Define is_golden_record como False para todos os registros de um dado normalizado, exceto um ID."""
        logger.debug(f"Desativando GRs para dado='{dado_normalizado}', tipo='{tipo_validacao}', exceto ID='{exclude_id}'")
        for rec in self._records.values():
            if rec.dado_normalizado == dado_normalizado and rec.tipo_validacao == tipo_validacao:
                if rec.id != exclude_id and rec.is_golden_record:
                    rec.is_golden_record = False
                    rec.updated_at = datetime.now(timezone.utc)
                    # Em um DB real, você faria um UPDATE aqui

    async def update_golden_record_status(self, record_id: int, is_golden: bool, golden_record_id: Optional[int]):
        """Atualiza o status de golden_record e golden_record_id para um registro específico."""
        record = self._records.get(record_id)
        if record:
            record.is_golden_record = is_golden
            record.golden_record_id = golden_record_id
            record.updated_at = datetime.now(timezone.utc)
            logger.debug(f"Status GR atualizado para registro {record_id}: is_golden={is_golden}, golden_id={golden_record_id}")
            # Em um DB real, você faria um UPDATE aqui
        else:
            logger.warning(f"Tentativa de atualizar status GR para registro inexistente: {record_id}")

    async def get_records_by_app_name(self, app_name: str, limit: int = 10, include_deleted: bool = False) -> List[ValidationRecord]:
        """Retorna registros filtrados por app_name."""
        records = [rec for rec in self._records.values() if rec.app_name == app_name and (include_deleted or not rec.is_deleted)]
        records.sort(key=lambda r: r.data_validacao, reverse=True)
        return records[:limit]