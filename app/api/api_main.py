# app/api/api_main.py
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any
# Importações organizadas
from app.config.settings import settings
from app.database.manager import DatabaseManager
from app.database.repositories import ValidationRecordRepository
from app.database.schema import initialize_database 
from app.auth.api_key_manager import APIKeyManager
from app.rules.decision_rules import DecisionRules
from app.services.validation_service import ValidationService

# Importação dos modelos de requisição e registro
from app.services.validation_service import UniversalValidationRequest # Importa UniversalValidationRequest do service mockado para compatibilidade
# Em um ambiente real, UniversalValidationRequest estaria em um módulo como app.models.schemas

# Importação dos validadores existentes
from app.rules.phone.validator import PhoneValidator
from app.rules.address.cep.validator import CEPValidator # Assegure-se de que este CEPValidator existe e é o correto
from app.rules.email.validator import EmailValidator
from app.rules.document.cpf_cnpj.validator import CpfCnpjValidator
from app.rules.address.address_validator import AddressValidator

# NOVOS: Importação dos validadores de nome, sexo, RG e data de nascimento
from app.rules.pessoa.nome.validator import NomeValidator
from app.rules.pessoa.genero.validator import SexoValidator
from app.rules.person.rg.validator import RGValidator # CORREÇÃO AQUI: Importando RGValidator de seu local dedicado
from app.rules.pessoa.data_nascimento.validator import DataNascimentoValidator

# Importa o LogRepository
from Validation_Barramento.app.database.repositories.log_repository import LogRepository
from Validation_Barramento.app.database.repositories.log_repository import LogEntry # Importa LogEntry para uso em handlers de exceção


# --- Configuração de Logging Centralizada ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# --- Gerenciador de Ciclo de Vida (Lifespan) Robusto ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    Inicializa recursos na partida e os libera de forma segura no desligamento.
    """
    logger.info("Fase de STARTUP do Lifespan iniciada... (main.py)")
    
    # Obtém a instância singleton do DatabaseManager.
    db_manager = DatabaseManager.get_instance() 
    
    try:
        await db_manager.connect(settings.DATABASE_URL) 

        # CORREÇÃO CRÍTICA: Passa a instância do DatabaseManager para initialize_database
        await initialize_database(db_manager) 
        logger.info("Schema do banco de dados inicializado com sucesso.")

        validation_repo = ValidationRecordRepository(db_manager) 
        log_repo = LogRepository(db_manager) # Instancia o LogRepository
        
        # api_key_manager precisa do caminho do arquivo settings.API_KEYS_FILE
        # Em um ambiente real, settings.API_KEYS_FILE conteria o caminho para o arquivo de chaves de API
        # Para este exemplo com mocks, vamos fornecer a configuração diretamente.
        API_KEYS_SYSTEMS_ENV_MOCK = {
            "API_KEY_SEGUROS": {"app_name": "Sistema de Seguros", "can_delete_records": False, "can_check_duplicates": False, "can_request_enrichment": False},
            "API_KEY_FINANCAS": {"app_name": "Sistema de Financas", "can_delete_records": True, "access_level": "admin", "can_check_duplicates": True, "can_request_enrichment": True},
            "API_KEY_PSDC": {"app_name": "Sistema de PSDC", "can_delete_records": True, "access_level": "psdc", "can_check_duplicates": True, "can_request_enrichment": True}
        }
        api_key_manager = APIKeyManager(API_KEYS_SYSTEMS_ENV_MOCK) 
        
        decision_rules = DecisionRules(repo=validation_repo) 

        # Os validadores são instanciados aqui e passados para o ValidationService
        phone_validator = PhoneValidator()
        cep_validator = CEPValidator()
        email_validator = EmailValidator()
        cpf_cnpj_validator = CpfCnpjValidator()
        
        address_validator = AddressValidator(cep_validator=cep_validator)
        
        nome_validator = NomeValidator()
        sexo_validator = SexoValidator()
        rg_validator = RGValidator() # RGValidator instanciado
        data_nascimento_validator = DataNascimentoValidator()
        
        # O ValidationService depende de todas as instâncias injetáveis
        validation_service = ValidationService(
            api_key_manager=api_key_manager,
            repo=validation_repo, 
            decision_rules=decision_rules,
            phone_validator=phone_validator,
            cep_validator=cep_validator,
            email_validator=email_validator,
            cpf_cnpj_validator=cpf_cnpj_validator,
            address_validator=address_validator,
            nome_validator=nome_validator,
            sexo_validator=sexo_validator,
            rg_validator=rg_validator, # RGValidator passado para o serviço
            data_nascimento_validator=data_nascimento_validator,
            log_repo=log_repo # Passa o LogRepository para o ValidationService
        )

        # Armazenar instâncias no estado da aplicação para que os endpoints possam acessá-las
        app.state.db_manager = db_manager
        app.state.validation_service = validation_service
        app.state.api_key_manager = api_key_manager
        app.state.log_repo = log_repo # Armazenar o log_repo no estado da aplicação

        logger.info("Fase de STARTUP do Lifespan concluída. Aplicação pronta para receber requisições.")
        
        yield # A aplicação fica em execução aqui

    finally:
        logger.info("Fase de SHUTDOWN do Lifespan iniciada...")
        
        if getattr(app.state, 'db_manager', None) and app.state.db_manager.is_connected:
            await app.state.db_manager.close()
            logger.info("Pool de conexões com o banco de dados fechado.")
            
        logger.info("Fase de SHUTDOWN do Lifespan concluída.")

# --- Instância da Aplicação FastAPI ---
app = FastAPI(
    title="Barramento de Validação de Dados",
    version="1.0.0",
    description="Uma API robusta para validar e enriquecer dados diversos.",
    lifespan=lifespan
)

# --- Middleware de Autenticação ---
class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith(("/docs", "/openapi.json", "/redoc")): 
            return await call_next(request)

        api_key = request.headers.get("x-api-key")
        if not api_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                content={"detail": "API Key ausente."}
            )
        
        api_key_manager: APIKeyManager = getattr(request.app.state, 'api_key_manager', None)
        if not api_key_manager:
            logger.error("APIKeyManager não disponível no estado da aplicação durante o middleware.")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Configuração interna do servidor falhou."}
            )

        app_info: Dict[str, Any] = api_key_manager.get_app_info(api_key)
        
        if not app_info:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                content={"detail": "API Key inválida ou não autorizada."}
            )

        request.state.app_info = app_info
        request.state.auth_app_name = app_info.get("app_name") 
        request.state.can_delete_records = app_info.get("can_delete_records", False)
        request.state.can_check_duplicates = app_info.get("can_check_duplicates", False) # Adicionado para uso na lógica de GR/duplicatas
        
        logger.info(f"API Key '{request.state.auth_app_name}' autenticada para o caminho '{path}'.")

        return await call_next(request)

app.add_middleware(APIKeyAuthMiddleware)

# --- Manipuladores de Exceção Globais ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception em '{request.url.path}': {exc.status_code} - {exc.detail}")
    # ADICIONAR LOG DE ERRO HTTP AQUI
    log_repo = getattr(request.app.state, 'log_repo', None)
    if log_repo:
        await log_repo.add_log_entry(
            LogEntry(
                tipo_evento="ERRO_HTTP",
                app_origem=request.state.auth_app_name if hasattr(request.state, 'auth_app_name') else "Desconhecido",
                usuario_operador=None, # Pode ser populado se você tiver um token de usuário
                detalhes_evento_json={"path": request.url.path, "status_code": exc.status_code, "detail": exc.detail},
                status_operacao="FALHA",
                mensagem_log=f"Erro HTTP {exc.status_code}: {exc.detail}"
            )
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.critical(f"Erro inesperado (Exceção Geral) em '{request.url.path}': {exc}", exc_info=True)
    # ADICIONAR LOG DE ERRO GERAL AQUI
    log_repo = getattr(request.app.state, 'log_repo', None)
    if log_repo:
        await log_repo.add_log_entry(
            LogEntry(
                tipo_evento="ERRO_INTERNO_FATAL",
                app_origem=request.state.auth_app_name if hasattr(request.state, 'auth_app_name') else "Desconhecido",
                usuario_operador=None, # Pode ser populado
                detalhes_evento_json={"path": request.url.path, "exception_type": type(exc).__name__, "exception_message": str(exc)},
                status_operacao="FALHA",
                mensagem_log=f"Erro interno fatal: {str(exc)}"
            )
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Ocorreu um erro interno inesperado. A equipe de desenvolvimento foi notificada."}
    )

# --- Rotas da API ---
@app.get("/", summary="Raiz da API", tags=["Status"])
async def root():
    return {"message": "Bem-vindo ao Barramento de Validação de Dados"}

# --- INCLUIR TODOS OS SEUS APIRouters AQUI ---
# Estas linhas REGISTRAM as rotas definidas em health.py, history.py, validation.py
# Elas são essenciais para que os endpoints /api/v1/health, /api/v1/history, /api/v1/validate etc.
# sejam reconhecidos pela aplicação FastAPI.
from Validation_Barramento.app.api.schemas.health import router as health_router
from app.api.routers.history import router as history_router
from app.api.routers.validation import router as validation_router

app.include_router(health_router, prefix="/api/v1") 
app.include_router(history_router, prefix="/api/v1") 
app.include_router(validation_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")

