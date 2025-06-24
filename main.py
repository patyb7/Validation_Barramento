# main.py

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
from app.database.schema import initialize_database_schema
from app.auth.api_key_manager import APIKeyManager
from app.rules.decision_rules import DecisionRules
from app.services.validation_service import ValidationService
from app.rules.phone.validator import PhoneValidator
from app.rules.address.cep.validator import CEPValidator
from app.rules.email.validator import EmailValidator
from app.rules.document.cpf_cnpj.validator import CpfCnpjValidator

# --- IMPORTAR OS APIRouter DE CADA ARQUIVO DE ROTA ---
# ESTAS LINHAS SÃO CRÍTICAS PARA QUE AS ROTAS SEJAM RECONHECIDAS
from app.api.routers.health import router as health_router
from app.api.routers.history import router as history_router
from app.api.routers.validation import router as validation_router

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
    logger.info("Fase de STARTUP do Lifespan iniciada...")
    
    # Obtém a instância singleton do DatabaseManager.
    db_manager = DatabaseManager.get_instance() 
    
    try:
        await db_manager.connect(settings.DATABASE_URL)

        async with db_manager.get_connection() as conn:
            await initialize_database_schema(conn)
        logger.info("Schema do banco de dados inicializado com sucesso.")

        validation_repo = ValidationRecordRepository(db_manager)
        api_key_manager = APIKeyManager(settings.API_KEYS)
        decision_rules = DecisionRules(repo=validation_repo) 
        
        validation_service = ValidationService(
            api_key_manager=api_key_manager,
            repo=validation_repo,
            decision_rules=decision_rules, # Reutiliza a instância
            phone_validator=PhoneValidator(),
            cep_validator=CEPValidator(),
            email_validator=EmailValidator(),
            cpf_cnpj_validator=CpfCnpjValidator()
        )

        app.state.db_manager = db_manager
        app.state.validation_service = validation_service
        app.state.api_key_manager = api_key_manager

        logger.info("Fase de STARTUP do Lifespan concluída. Aplicação pronta para receber requisições.")
        
        yield # A aplicação fica em execução aqui

    finally:
        logger.info("Fase de SHUTDOWN do Lifespan iniciada...")
        
        if getattr(app.state, 'db_manager', None):
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
        # Rotas de documentação permanecem públicas. O endpoint /health AGORA exige API Key.
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

        request.state.auth_app_name = app_info.get("app_name")
        request.state.can_delete_records = app_info.get("can_delete_records", False)
        
        logger.info(f"API Key '{request.state.auth_app_name}' autenticada para o caminho '{path}'.")

        if path.startswith("/api/v1/records/") and ("soft-delete" in path or "restore" in path):
            if not request.state.can_delete_records:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    content={"detail": "Permissão negada para esta operação."}
                )

        return await call_next(request)

app.add_middleware(APIKeyAuthMiddleware)

# --- Manipuladores de Exceção Globais ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception em '{request.url.path}': {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.critical(f"Erro inesperado (Exceção Geral) em '{request.url.path}': {exc}", exc_info=True)
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
app.include_router(health_router, prefix="/api/v1") 
app.include_router(history_router, prefix="/api/v1") 
app.include_router(validation_router, prefix="/api/v1") 
