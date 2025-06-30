# app/api/api_main.py
import logging
from typing import Optional
from fastapi import FastAPI, Header, status, HTTPException, Request

# Importações internas do projeto (Caminhos absolutos para consistência)
from app.services.validation_service import ValidationService
from app.auth.api_key_manager import APIKeyManager
from app.database.manager import DatabaseManager
from app.database.repositories import ValidationRecordRepository
from app.rules.decision_rules import DecisionRules
from app.config.settings import settings
from app.database.schema import initialize_database_schema as initialize_database
from app.rules.phone.validator import PhoneValidator
from app.rules.address.cep.validator import CEPValidator
from app.rules.email.validator import EmailValidator
from app.rules.document.cpf_cnpj.validator import CpfCnpjValidator
from app.rules.address.validator import AddressValidator
from .routers import validation
from .routers import history
from .routers import health

# Configuração de logging.
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Variáveis Globais para as Dependências ---
# Declaradas como Optional e inicializadas como None.
# Serão preenchidas durante o evento de startup.
api_key_manager: Optional[APIKeyManager] = None
db_manager: Optional[DatabaseManager] = None
repo: Optional[ValidationRecordRepository] = None
decision_rules: Optional[DecisionRules] = None
val_service: Optional[ValidationService] = None

# Instâncias dos validadores que serão criadas no startup e injetadas no ValidationService
# Devem ser Optional[TipoValidador] para que possam ser None antes do startup
phone_validator: Optional[PhoneValidator] = None
cep_validator: Optional[CEPValidator] = None
email_validator: Optional[EmailValidator] = None
cpf_cnpj_validator: Optional[CpfCnpjValidator] = None
address_validator: Optional[AddressValidator] = None


# --- Constantes de Mensagem ---
INVALID_API_KEY_MESSAGE = "API Key inválida ou não autorizada."
MISSING_API_KEY_MESSAGE = "API Key faltando no cabeçalho 'x-api-key'."
AUTH_SERVICE_NOT_READY_MESSAGE = "Serviço de autenticação não está pronto. Tente novamente mais tarde."
VALIDATION_SERVICE_NOT_READY_MESSAGE = "Serviço de validação não está pronto. Tente novamente mais tarde."
PERMISSION_DENIED_MESSAGE = "Você não tem permissão para realizar esta operação."

# --- Inicializa o aplicativo FastAPI ---
app = FastAPI(
    title="Serviço de Validação Universal",
    description="Serviço centralizado para validar diversos tipos de dados (telefone, endereço, CPF/CNPJ, e-mail) com controle de regras por código e autenticação por API Key. Inclui funcionalidade de soft delete.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)
app.include_router(validation.router)
app.include_router(history.router)
app.include_router(health.router)
@app.on_event("startup")
async def startup_event():
    global api_key_manager, db_manager, repo, decision_rules, val_service
    global phone_validator, cep_validator, email_validator, cpf_cnpj_validator, address_validator

    logger.info("Iniciando processo de startup da aplicação...")
    try:
        logger.info("Inicializando DatabaseManager com a URL do banco de dados...")
        db_url = settings.DATABASE_URL

        # **NOVA FORMA DE INICIALIZAR O SINGLETON**
        db_manager = DatabaseManager.get_instance() # Apenas obtém a instância
        await db_manager.initialize(database_url=db_url) # E a inicializa com a URL correta

        logger.info("DatabaseManager: Pool de conexões estabelecido.")

    except Exception as e:
        logger.critical(f"Falha CRÍTICA ao inicializar DatabaseManager ou conectar ao DB: {e}. Aplicação não pode continuar.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha na inicialização do banco de dados: {e}"
        )
    # --- 2. Inicialização do Esquema do Banco de Dados ---
    try:
        logger.info("Verificando e inicializando esquema do banco de dados...")
        await initialize_database(db_manager)
        logger.info("Esquema do banco de dados verificado/inicializado com sucesso.")
    except Exception as e:
        logger.critical(f"Falha CRÍTICA ao inicializar o esquema do banco de dados: {e}. Encerrando a aplicação.", exc_info=True)
        if db_manager:
            try:
                await db_manager.close_pool()
            except Exception as close_e:
                logger.error(f"Erro ao fechar pool de conexões durante falha de startup: {close_e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha na inicialização do esquema do banco de dados: {e}"
        )

    # --- 3. Inicialização dos Outros Serviços e Validadores ---
    try:
        logger.info("Inicializando ValidationRecordRepository...")
        repo = ValidationRecordRepository(db_manager=db_manager)
        logger.info("ValidationRecordRepository inicializado.")

        logger.info("Inicializando APIKeyManager...")
        # Assegura que APIKeyManager recebe as chaves da configuração
        api_key_manager = APIKeyManager(settings.API_KEYS)
        logger.info("APIKeyManager inicializado.")

        logger.info("Inicializando DecisionRules...")
        decision_rules = DecisionRules(repo) # Passa o repositório
        logger.info("DecisionRules inicializado.")

        # Instanciação dos Validadores, passando db_manager se necessário
        # Assumindo que os construtores dos Validadores aceitam db_manager
        logger.info("Inicializando validadores de dados...")
        phone_validator = PhoneValidator(db_manager=db_manager)
        cep_validator = CEPValidator(db_manager=db_manager)
        email_validator = EmailValidator(db_manager=db_manager)
        cpf_cnpj_validator = CpfCnpjValidator(db_manager=db_manager)
        # O AddressValidator pode depender do CEPValidator, ou ambos do db_manager
        address_validator = AddressValidator(db_manager=db_manager, cep_validator=cep_validator) # Exemplo: pode receber db_manager e cep_validator
        logger.info("Validadores inicializados.")

        logger.info("Inicializando ValidationService com validadores injetados...")
        val_service = ValidationService(
            api_key_manager=api_key_manager,
            repo=repo,
            decision_rules=decision_rules,
            phone_validator=phone_validator,
            cep_validator=cep_validator,
            email_validator=email_validator,
            cpf_cnpj_validator=cpf_cnpj_validator,
            address_validator=address_validator
        )
        logger.info("Serviços principais inicializados com sucesso.")

    except Exception as e:
        logger.critical(f"Falha CRÍTICA na inicialização de um ou mais serviços dependentes: {e}. Encerrando.", exc_info=True)
        if db_manager:
            try:
                await db_manager.close_pool()
            except Exception as close_e:
                logger.error(f"Erro ao fechar pool de conexões durante falha de startup: {close_e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha na inicialização dos serviços: {e}"
        )

    logger.info("Startup da aplicação concluído.")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Iniciando processo de shutdown da aplicação...")
    if db_manager:
        try:
            await db_manager.close_pool()
            logger.info("Pool de conexões do DatabaseManager fechado.")
        except Exception as e:
            logger.error(f"Erro ao fechar pool de conexões no shutdown: {e}", exc_info=True)
    else:
        logger.info("DatabaseManager não inicializado; nenhum pool de conexões para fechar.")

    logger.info("Shutdown da aplicação concluído.")

AUTH_EXEMPT_PATHS = ["/", "/docs", "/redoc", "/openapi.json", "/health", "/api/v1/health"]

@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    logger.debug(f"Middleware: Requisição recebida para o caminho: {request.url.path}")

    # Verifica se o caminho da requisição está isento de autenticação
    if request.url.path in AUTH_EXEMPT_PATHS or request.url.path.startswith("/api/v1/health"):
        return await call_next(request)

    # Verifica se o APIKeyManager foi inicializado
    if api_key_manager is None:
        logger.critical("Middleware: APIKeyManager não inicializado. Erro de configuração da aplicação.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_NOT_READY_MESSAGE
        )

    # Obtém a API Key do cabeçalho
    api_key_header = request.headers.get("x-api-key")
    if not api_key_header:
        logger.warning(f"Middleware: Acesso não autorizado. API Key faltando para {request.url.path}.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MISSING_API_KEY_MESSAGE
        )

    # Valida a API Key
    app_info = api_key_manager.get_app_info(api_key_header)
    if not app_info:
        logger.warning(f"Middleware: Acesso não autorizado. API Key inválida: {api_key_header[:5]}... (primeiros 5 caracteres).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_API_KEY_MESSAGE
        )

    # Armazena informações da API Key no estado da requisição para uso posterior
    request.state.auth_app_name = app_info.get("app_name")
    request.state.can_delete_records = app_info.get("can_delete_records", False)
    request.state.access_level = app_info.get("access_level", "default")
    request.state.can_check_duplicates = app_info.get("can_check_duplicates", False)
    request.state.can_request_enrichment = app_info.get("can_request_enrichment", False)


    logger.info(f"Middleware: API Key '{request.state.auth_app_name}' autenticada para {request.url.path}. Permissões: can_delete_records={request.state.can_delete_records}, access_level='{request.state.access_level}', can_check_duplicates={request.state.can_check_duplicates}, can_request_enrichment={request.state.can_request_enrichment}.")

    # Lógica de autorização baseada no caminho e permissões
    # Exemplo: Requer permissão para 'soft-delete' ou 'restore'
    if request.url.path.startswith("/api/v1/records/") and \
       ("soft-delete" in request.url.path or "restore" in request.url.path):
        if not request.state.can_delete_records:
            logger.warning(f"Middleware: Acesso negado para '{request.state.auth_app_name}'. Não possui permissão para deletar/restaurar registros em {request.url.path}.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=PERMISSION_DENIED_MESSAGE
            )

    # Prossegue com a requisição
    response = await call_next(request)
    return response