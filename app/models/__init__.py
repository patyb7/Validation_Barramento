# app/models/__init__.py
# Importa modelos Pydantic para exposição
from .validation_record import ValidationRecord
from .client_entity import ClientEntity
from .golden_record_summary import GoldenRecordSummary

# Se você quiser que os modelos ORM do SQLAlchemy também sejam acessíveis via `app.models`,
# importe-os aqui e renomeie-os para evitar conflito com os Pydantic models.
# Exemplo:
# from ..database.schema import ValidationRecord as DBValidationRecord
# from ..database.schema import ClientEntity as DBClientEntity

__all__ = [
    "ValidationRecord",
    "ClientEntity",
    "GoldenRecordSummary",
    # "DBValidationRecord",  # Se você decidiu exportá-los também
    # "DBClientEntity",
]