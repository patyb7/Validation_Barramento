import logging
from app.rules.document.cpf_cnpj.validator import CpfCnpjValidator
from app.rules.email.validator import EmailValidator
from app.services.validation.record_service import ValidationRecordService
from app.repositories.validation_record_repository import ValidationRecordRepository
from app.database import database as db # Assumindo que você tem um módulo de conexão com o DB Barramento

logger = logging.getLogger(__name__)

class BarramentoConfig:
    """
    Configuração e inicialização centralizada dos componentes do Barramento.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BarramentoConfig, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        logger.info("Inicializando componentes do Barramento...")
        self.cpf_cnpj_validator = CpfCnpjValidator()
        self.email_validator = EmailValidator()
        
        # O repositório real que interage com a base de dados "Barramento"
        # Você precisaria ter a sua lógica de conexão com o banco de dados aqui.
        # Por exemplo, se usa SQLAlchemy:
        # self.db_session = db.get_session() 
        # self.validation_record_repo = ValidationRecordRepository(self.db_session)

        # Por enquanto, usaremos um repositório em memória para a simulação
        # ou você pode passar o seu repositório de DB real aqui.
        self.validation_record_repo = ValidationRecordRepository() # Ajuste se o construtor precisar de session/conn
        
        self.validation_record_service = ValidationRecordService(
            cpf_cnpj_validator=self.cpf_cnpj_validator,
            email_validator=self.email_validator,
            validation_record_repository=self.validation_record_repo
        )
        logger.info("Componentes do Barramento inicializados.")

    def get_validation_service(self) -> ValidationRecordService:
        return self.validation_record_service

# Exemplo de como usar (singleton)
barramento_instance = BarramentoConfig()