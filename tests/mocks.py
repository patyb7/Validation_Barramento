# tests/mocks.py

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, Optional, List
from pydantic import UUID4

# Importar seus modelos Pydantic reais
from app.models.validation_record import ValidationRecord
from app.models.qualificacao_pendente import QualificacaoPendente, InvalidosQualificados
from app.models.log_entry import LogEntry

# --- Mocks de Modelos Auxiliares (se não forem Pydantic Models reais) ---
# Mantendo MockClientEntity pois não foi fornecida uma definição Pydantic real para ela.
# Se ClientEntity fosse um Pydantic BaseModel real, você o importaria aqui e usaria diretamente.
class MockClientEntity(MagicMock):
    """
    Mock para simular o modelo ClientEntity.
    Assumimos que ele se comporta como um Pydantic BaseModel para fins de teste.
    """
    def __init__(self, **data):
        super().__init__()
        self.id: UUID4 = data.get("id") or uuid.uuid4()
        self.main_document_normalized: str = data.get("main_document_normalized")
        self.consolidated_data: Dict[str, Any] = data.get("consolidated_data", {})
        self.golden_record_cpf_cnpj_id: Optional[UUID4] = data.get("golden_record_cpf_cnpj_id")
        self.golden_record_celular_id: Optional[UUID4] = data.get("golden_record_celular_id")
        self.golden_record_email_id: Optional[UUID4] = data.get("golden_record_email_id")
        self.golden_record_endereco_id: Optional[UUID4] = data.get("golden_record_endereco_id")
        self.golden_record_cep_from_address_id: Optional[UUID4] = data.get("golden_record_cep_from_address_id")
        self.created_at: datetime = data.get("created_at") or datetime.now(timezone.utc)
        self.updated_at: datetime = data.get("updated_at") or datetime.now(timezone.utc)

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:
        """Simula o método .model_dump() de um Pydantic BaseModel."""
        return {
            "id": str(self.id),
            "main_document_normalized": self.main_document_normalized,
            "consolidated_data": self.consolidated_data,
            "golden_record_cpf_cnpj_id": str(self.golden_record_cpf_cnpj_id) if self.golden_record_cpf_cnpj_id else None,
            "golden_record_celular_id": str(self.golden_record_celular_id) if self.golden_record_celular_id else None,
            "golden_record_email_id": str(self.golden_record_email_id) if self.golden_record_email_id else None,
            "golden_record_endereco_id": str(self.golden_record_endereco_id) if self.golden_record_endereco_id else None,
            "golden_record_cep_from_address_id": str(self.golden_record_cep_from_address_id) if self.golden_record_cep_from_address_id else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

class MockValidationRecordRepository(AsyncMock):
    """
    Mock para o repositório de ValidationRecord, simulando operações de banco de dados.
    Armazena instâncias do ValidationRecord real para fidelidade.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._records: Dict[str, ValidationRecord] = {}

    async def create_record(self, record_instance: ValidationRecord) -> ValidationRecord:
        """Simula a criação de um novo ValidationRecord no DB."""
        new_record = ValidationRecord(**record_instance.model_dump())
        if not new_record.id:
            new_record.id = uuid.uuid4()
        new_record.created_at = datetime.now(timezone.utc)
        new_record.updated_at = datetime.now(timezone.utc)
        new_record.model_post_init(None) # Garante que hooks Pydantic sejam chamados
        self._records[str(new_record.id)] = new_record
        return new_record

    async def get_record(self, record_id: UUID4) -> Optional[ValidationRecord]:
        """Simula a busca de um ValidationRecord pelo ID."""
        return self._records.get(str(record_id))

    async def update_record(self, record_id: UUID4, updates: Dict[str, Any]) -> Optional[ValidationRecord]:
        """Simula a atualização de um ValidationRecord no DB."""
        record = self._records.get(str(record_id))
        if record:
            for k, v in updates.items():
                setattr(record, k, v)
            record.updated_at = datetime.now(timezone.utc)
            record.model_post_init(None) # Re-chama hooks após atualização
            return record
        return None

class MockQualificationRepository(AsyncMock):
    """
    Mock para o repositório de Qualificação, simulando operações relacionadas a
    ClientEntity, QualificacaoPendente e InvalidosQualificados.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client_entities: Dict[str, MockClientEntity] = {}
        self._pending_qualifications: Dict[str, QualificacaoPendente] = {}
        self._invalidos_qualificados: Dict[str, InvalidosQualificados] = {}

    async def get_client_entity_by_main_document(self, main_document_normalized: str) -> Optional[MockClientEntity]:
        """Simula a busca de uma entidade cliente pelo documento principal."""
        for entity_id, entity_instance in self._client_entities.items():
            if entity_instance.main_document_normalized == main_document_normalized:
                return entity_instance
        return None

    async def create_client_entity(self, data: Dict[str, Any]) -> MockClientEntity:
        """Simula a criação de uma nova entidade cliente."""
        new_entity = MockClientEntity(**data)
        new_entity.id = uuid.uuid4()
        new_entity.created_at = datetime.now(timezone.utc)
        new_entity.updated_at = datetime.now(timezone.utc)
        self._client_entities[str(new_entity.id)] = new_entity
        return new_entity

    async def update_client_entity(self, entity_id: UUID4, updates: Dict[str, Any]) -> Optional[MockClientEntity]:
        """Simula a atualização de uma entidade cliente existente."""
        entity = self._client_entities.get(str(entity_id))
        if entity:
            for k, v in updates.items():
                setattr(entity, k, v)
            entity.updated_at = datetime.now(timezone.utc)
            return entity
        return None

    async def create_pending_qualification(self, pending_qual_instance: QualificacaoPendente) -> QualificacaoPendente:
        """Simula a criação de uma nova qualificação pendente."""
        new_pq = QualificacaoPendente(**pending_qual_instance.model_dump())
        if not new_pq.id:
            new_pq.id = uuid.uuid4()
        new_pq.created_at = datetime.now(timezone.utc)
        new_pq.updated_at = datetime.now(timezone.utc)
        self._pending_qualifications[str(new_pq.id)] = new_pq
        return new_pq

    async def get_pending_qualification_by_record_id(self, validation_record_id: UUID4) -> Optional[QualificacaoPendente]:
        """Simula a busca de uma qualificação pendente pelo ID do ValidationRecord."""
        for pq in self._pending_qualifications.values():
            if pq.validation_record_id == validation_record_id:
                return pq
        return None

    async def create_invalidos_qualificados(self, invalidos_qualificados_instance: InvalidosQualificados) -> InvalidosQualificados:
        """Simula a criação de um registro de dado inválido/desqualificado."""
        new_iq = InvalidosQualificados(**invalidos_qualificados_instance.model_dump())
        if not new_iq.id:
            new_iq.id = uuid.uuid4()
        new_iq.archived_at = datetime.now(timezone.utc)
        self._invalidos_qualificados[str(new_iq.id)] = new_iq
        return new_iq

class MockLogEntryRepository(AsyncMock):
    """
    Mock para o repositório de LogEntry, simulando a persistência de logs de auditoria.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._log_entries: Dict[str, LogEntry] = {}

    async def create_log_entry(self, log_entry_instance: LogEntry) -> LogEntry:
        """Simula a criação de uma nova entrada de log."""
        new_log = LogEntry(**log_entry_instance.model_dump())
        if not new_log.id:
            new_log.id = uuid.uuid4()
        new_log.created_at = datetime.now(timezone.utc)
        new_log.timestamp_evento = datetime.now(timezone.utc)
        self._log_entries[str(new_log.id)] = new_log
        return new_log

    async def get_log_entry(self, log_id: UUID4) -> Optional[LogEntry]:
        """Simula a busca de uma entrada de log pelo ID."""
        return self._log_entries.get(str(log_id))

    async def get_log_entries_by_event_type(self, event_type: str) -> List[LogEntry]:
        """Simula a busca de entradas de log por tipo de evento."""
        return [log for log in self._log_entries.values() if log.tipo_evento == event_type]

    async def get_log_entries_by_related_record_id(self, related_record_id: UUID4) -> List[LogEntry]:
        """Simula a busca de entradas de log por ID de registro relacionado."""
        return [log for log in self._log_entries.values() if log.related_record_id == related_record_id]
### Validadores Individuais Mocks

class MockPhoneValidator(AsyncMock):
    """
    Mock para o validador de telefone, simulando diferentes resultados de validação.
    """
    async def validate(self, phone_number: str, **kwargs) -> Dict[str, Any]:
        """Simula a validação de um número de telefone."""
        result = {
            "is_valid": True,
            "dado_original": phone_number,
            "dado_normalizado": phone_number.replace(" ", "").replace("-", ""),
            "mensagem": "Telefone válido.",
            "details": {},
            "business_rule_applied": {"code": "RN_TEL001", "type": "Telefone", "name": "Telefone Encontrado na Base"}
        }
        if "INVALID_TEL" in phone_number:
            result["is_valid"] = False
            result["mensagem"] = "Número de telefone inválido para teste."
            result["business_rule_applied"]["code"] = "RN_TEL000"
            result["business_rule_applied"]["name"] = "Telefone Inválido"
        elif phone_number == "11999999999":
            result["business_rule_applied"]["code"] = "RN_TEL004"
            result["business_rule_applied"]["name"] = "Telefone Válido (Formato) - Não Encontrado"
            result["mensagem"] = "Telefone válido (formato), mas não encontrado na base cadastral simulada."
        return result

class MockEmailValidator(AsyncMock):
    """
    Mock para o validador de e-mail, simulando diferentes resultados de validação.
    """
    async def validate(self, email: str, **kwargs) -> Dict[str, Any]:
        """Simula a validação de um endereço de e-mail."""
        result = {
            "is_valid": True,
            "dado_original": email,
            "dado_normalizado": email.lower(),
            "mensagem": "Email válido.",
            "details": {},
            "business_rule_applied": {"code": "RN_EMAIL002", "type": "Email", "name": "Domínio Resolvível"}
        }
        if "@invalid.com" in email:
            result["is_valid"] = False
            result["mensagem"] = "Domínio de email inválido."
            result["business_rule_applied"]["code"] = "RN_EMAIL001"
            result["business_rule_applied"]["name"] = "Domínio de Email Inválido"
        return result

class MockCpfCnpjValidator(AsyncMock):
    """
    Mock para o validador de CPF/CNPJ.
    """
    async def validate(self, document_number: str, **kwargs) -> Dict[str, Any]:
        """Simula a validação de um CPF ou CNPJ."""
        # Valor padrão para CPF válido
        result = {
            "is_valid": True,
            "dado_original": document_number,
            "dado_normalizado": document_number.replace(".", "").replace("-", "").replace("/", ""),
            "mensagem": "Documento válido e encontrado.",
            "details": {},
            "business_rule_applied": {"code": "RN_DOC001", "type": "Documento", "name": "Documento Válido e Encontrado"}
        }
        if "INVALID_DOC" in document_number:
            result["is_valid"] = False
            result["mensagem"] = "Documento inválido para teste."
            result["business_rule_applied"]["code"] = "RN_DOC000"
            result["business_rule_applied"]["name"] = "Documento Inválido"
            result["dado_normalizado"] = None
        return result

class MockAddressValidator(AsyncMock):
    """
    Mock para o validador de endereço.
    """
    async def validate(self, address_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Simula a validação de um endereço."""
        result = {
            "is_valid": True,
            "dado_original": address_data,
            "dado_normalizado": {**address_data, "bairro": "Centro Mock", "cidade": "Cidade Mock", "estado": "SP", "cep": address_data.get("cep", "12345678")},
            "mensagem": "Endereço válido e consistente.",
            "details": {"cep_validation": {"is_valid": True, "business_rule_applied": {"code": "RN_CEP001"}}},
            "business_rule_applied": {"code": "RN_ADDR001", "type": "Endereço", "name": "Endereço 100% Consistente"}
        }
        if "INVALID_ADDR" in address_data.get("logradouro", ""):
            result["is_valid"] = False
            result["mensagem"] = "Endereço inválido para teste."
            result["business_rule_applied"]["code"] = "RN_ADDR000"
            result["business_rule_applied"]["name"] = "Endereço Inválido"
        return result

class MockNomeValidator(AsyncMock):
    """
    Mock para o validador de nome.
    """
    async def validate(self, name: str, **kwargs) -> Dict[str, Any]:
        """Simula a validação de um nome."""
        result = {
            "is_valid": True,
            "dado_original": name,
            "dado_normalizado": name.upper(),
            "mensagem": "Nome válido.",
            "details": {},
            "business_rule_applied": {"code": "RN_NOM001", "type": "Nome", "name": "Nome Válido"}
        }
        if "INVALID_NAME" in name:
            result["is_valid"] = False
            result["mensagem"] = "Nome inválido para teste."
            result["business_rule_applied"]["code"] = "RN_NOM000"
            result["business_rule_applied"]["name"] = "Nome Inválido"
        return result

class MockSexoValidator(AsyncMock):
    """
    Mock para o validador de sexo.
    """
    async def validate(self, gender: str, **kwargs) -> Dict[str, Any]:
        """Simula a validação de sexo."""
        normalized_gender = "MASCULINO" if gender.upper().startswith("M") else "FEMININO" if gender.upper().startswith("F") else None
        is_valid = normalized_gender is not None

        result = {
            "is_valid": is_valid,
            "dado_original": gender,
            "dado_normalizado": normalized_gender,
            "mensagem": "Sexo válido." if is_valid else "Sexo inválido.",
            "details": {},
            "business_rule_applied": {"code": "RN_SEX001" if is_valid else "RN_SEX000", "type": "Sexo", "name": "Sexo Válido" if is_valid else "Sexo Inválido"}
        }
        return result

class MockRgValidator(AsyncMock):
    """
    Mock para o validador de RG.
    """
    async def validate(self, rg: str, **kwargs) -> Dict[str, Any]:
        """Simula a validação de um RG."""
        result = {
            "is_valid": True,
            "dado_original": rg,
            "dado_normalizado": rg.replace(".", "").replace("-", ""),
            "mensagem": "RG válido e ativo.",
            "details": {},
            "business_rule_applied": {"code": "RN_RG001", "type": "Documento", "name": "RG Válido e Ativo"}
        }
        if "INVALID_RG" in rg:
            result["is_valid"] = False
            result["mensagem"] = "RG inválido para teste."
            result["business_rule_applied"]["code"] = "RN_RG000"
            result["business_rule_applied"]["name"] = "RG Inválido"
        return result

class MockDataNascimentoValidator(AsyncMock):
    """
    Mock para o validador de data de nascimento.
    """
    async def validate(self, dob: str, **kwargs) -> Dict[str, Any]:
        """Simula a validação de uma data de nascimento."""
        result = {
            "is_valid": True,
            "dado_original": dob,
            "dado_normalizado": dob,
            "mensagem": "Data de nascimento válida.",
            "details": {},
            "business_rule_applied": {"code": "RN_DTN001", "type": "Data de Nascimento", "name": "Data de Nascimento Válida"}
        }
        try:
            # Simula uma data futura ou formato inválido
            date_obj = datetime.strptime(dob, "%Y-%m-%d").date()
            if date_obj > datetime.now(timezone.utc).date():
                result["is_valid"] = False
                result["mensagem"] = "Data de nascimento no futuro."
                result["business_rule_applied"]["code"] = "RN_DTN000"
                result["business_rule_applied"]["name"] = "Data de Nascimento Inválida"
        except ValueError:
            result["is_valid"] = False
            result["mensagem"] = "Formato de data de nascimento inválido."
            result["business_rule_applied"]["code"] = "RN_DTN000"
            result["business_rule_applied"]["name"] = "Data de Nascimento Inválida"
        return result

class MockCepValidator(AsyncMock):
    """
    Mock para o validador de CEP.
    """
    async def validate(self, cep: str, **kwargs) -> Dict[str, Any]:
        """Simula a validação de um CEP."""
        result = {
            "is_valid": True,
            "dado_original": cep,
            "dado_normalizado": cep.replace("-", ""),
            "mensagem": "CEP válido.",
            "details": {},
            "business_rule_applied": {"code": "RN_CEP001", "type": "CEP", "name": "CEP Válido"}
        }
        if "INVALID_CEP" in cep or len(cep.replace("-", "")) != 8:
            result["is_valid"] = False
            result["mensagem"] = "CEP inválido para teste."
            result["business_rule_applied"]["code"] = "RN_CEP000"
            result["business_rule_applied"]["name"] = "CEP Inválido"
        return result

class MockValidationRecordRepository:
    pass


