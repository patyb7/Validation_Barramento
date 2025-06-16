# app/api/api_main.py
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, Header, status, HTTPException
from starlette.requests import Request
from pydantic import BaseModel

# Importações internas do projeto para inicializar os serviços
from ..auth.api_key_manager import APIKeyManager
from ..database.manager import DatabaseManager
from ..database.repositories import ValidationRecordRepository
from ..rules.decision_rules import DecisionRules
from ..config.settings import settings 
from ..services.validation_service import ValidationService 
from ..database.schema import initialize_database # Usando a função mais limpa

# Importar validadores específicos para injetar no ValidationService
from ..rules.phone.validator import PhoneValidator
from ..rules.address.cep.validator import CEPValidator

# Configuração de logging.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Variáveis Globais para as Dependências do ValidationService ---
# Declaradas como Optional para que possam ser inicializadas durante o startup.
api_key_manager: Optional[APIKeyManager] = None
db_manager: Optional[DatabaseManager] = None
repo: Optional[ValidationRecordRepository] = None
decision_rules: Optional[DecisionRules] = None
val_service: Optional[ValidationService] = None # Nome da variável global para o serviço

# --- Inicializa o aplicativo FastAPI ---
app = FastAPI(
    title="Serviço de Validação Universal",
    description="Serviço centralizado para validar diversos tipos de dados (telefone, endereço, CPF/CNPJ, e-mail) com controle de regras por código e autenticação por API Key. Inclui funcionalidade de soft delete.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.on_event("startup")
async def startup_event():
    """
    Função executada na inicialização da aplicação FastAPI.
    """
    global api_key_manager, db_manager, repo, decision_rules, val_service

    logger.info("Iniciando processo de startup da aplicação...")

    # 1. Inicializa o DatabaseManager (instância singleton) e conecta ao DB
    try:
        logger.info("Inicializando DatabaseManager com a URL do banco de dados...")
        db_url = settings.DATABASE_URL 
        
        # Use o método de classe get_instance para obter/inicializar o singleton
        db_manager = DatabaseManager.get_instance(db_url=db_url) 
        # A mensagem "DatabaseManager instância criada." agora virá de get_instance

        # Conecta ao banco de dados e cria o pool de conexões.
        await db_manager.connect() 
        logger.info("DatabaseManager: Pool de conexões estabelecido.")

    except Exception as e:
        logger.critical(f"Falha CRÍTICA ao inicializar DatabaseManager ou conectar ao DB: {e}. Aplicação não pode continuar.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha na inicialização do banco de dados: {e}"
        ) 


    # 2. Inicializa o esquema do banco de dados (cria tabelas se não existirem)
    try:
        logger.info("Verificando e inicializando esquema do banco de dados...")
        await initialize_database(db_manager) 
        logger.info("Esquema do banco de dados verificado/inicializado com sucesso.")
    except Exception as e:
        logger.critical(f"Falha CRÍTICA ao inicializar o esquema do banco de dados: {e}. Encerrando a aplicação.", exc_info=True)
        # Tenta fechar o pool de conexões antes de levantar a exceção.
        if db_manager:
            try:
                await db_manager.close_pool() 
            except Exception as close_e:
                logger.error(f"Erro ao fechar pool de conexões durante falha de startup: {close_e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha na inicialização do esquema do banco de dados: {e}"
        ) 

    # 3. Inicializa os demais serviços que dependem do DB Manager e API Key Manager
    try:
        logger.info("Inicializando ValidationRecordRepository...")
        # CORREÇÃO AQUI: Passe a instância de db_manager inteira, não apenas o pool.
        repo = ValidationRecordRepository(db_manager=db_manager) # <<< MUDANÇA REALIZADA AQUI!
        logger.info("ValidationRecordRepository inicializado.")
        
        logger.info("Inicializando APIKeyManager...")
        # A settings.API_KEYS já lida com o fallback para Vault ou JSON.
        api_key_manager = APIKeyManager(settings.API_KEYS) 
        
        logger.info("Inicializando DecisionRules...")
        # Passa o repositório para as regras de decisão se elas precisarem interagir com o DB.
        decision_rules = DecisionRules(repo) 
        
        # Inicializa as instâncias dos validadores específicos para injeção no ValidationService.
        phone_validator = PhoneValidator()
        cep_validator = CEPValidator()

        logger.info("Inicializando ValidationService com validadores injetados...")
        # Injeta todas as dependências no ValidationService.
        val_service = ValidationService(
            api_key_manager=api_key_manager,
            repo=repo,
            decision_rules=decision_rules,
            phone_validator=phone_validator, # Injeta o validador de telefone
            cep_validator=cep_validator,     # Injeta o validador de CEP
            # Adicione outros validadores aqui conforme forem criados e injetados
        )
        
        logger.info("Serviços principais inicializados com sucesso.")
    except Exception as e:
        logger.critical(f"Falha CRÍTICA na inicialização de um ou mais serviços dependentes: {e}. Encerrando.", exc_info=True)
        # Tenta fechar o pool de conexões antes de levantar a exceção em caso de falha.
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
    """
    Função executada no desligamento da aplicação FastAPI.
    Responsável por liberar recursos, como conexões de banco de dados.
    """
    logger.info("Iniciando processo de shutdown da aplicação...")
    # Tenta fechar o pool de conexões do DatabaseManager, se ele foi inicializado.
    if db_manager:
        try:
            await db_manager.close_pool() 
            logger.info("Pool de conexões do DatabaseManager fechado.")
        except Exception as e:
            logger.error(f"Erro ao fechar pool de conexões no shutdown: {e}", exc_info=True)
    else:
        logger.info("DatabaseManager não inicializado; nenhum pool de conexões para fechar.")
    
    logger.info("Shutdown da aplicação concluído.")

### Middleware de Autenticação e Autorização de API Key

@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    logger.debug(f"Middleware: Requisição recebida para o caminho: {request.url.path}")

    # Rotas que NÃO precisam de autenticação de API Key
    AUTH_EXEMPT_PATHS = ["/", "/docs", "/redoc", "/openapi.json", "/health", "/api/v1/health"]
    if request.url.path in AUTH_EXEMPT_PATHS:
        response = await call_next(request)
        return response

    # Garante que api_key_manager foi inicializado antes de usá-lo.
    if api_key_manager is None:
        logger.critical("Middleware: APIKeyManager não inicializado. Erro de configuração da aplicação.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Serviço de autenticação não está pronto. Tente novamente mais tarde."
        )

    # Tenta obter a API Key do cabeçalho 'x-api-key'.
    api_key_header = request.headers.get("x-api-key")
    if not api_key_header:
        logger.warning(f"Middleware: Acesso não autorizado. API Key faltando para {request.url.path}.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key faltando no cabeçalho 'x-api-key'."
        )

    # Valida a API Key e obtém as informações da aplicação associada.
    app_info = api_key_manager.get_app_info(api_key_header)
    if not app_info:
        logger.warning(f"Middleware: Acesso não autorizado. API Key inválida: {api_key_header[:5]}... (primeiros 5 caracteres).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida ou não autorizada."
        )
    
    # Anexa as informações da aplicação ao estado da requisição para uso posterior nos endpoints.
    request.state.auth_app_name = app_info.get("app_name")
    request.state.can_delete_records = app_info.get("can_delete_records", False) 
    request.state.access_level = app_info.get("access_level", "default") 

    logger.info(f"Middleware: API Key '{request.state.auth_app_name}' autenticada para {request.url.path}. Permissões: can_delete_records={request.state.can_delete_records}, access_level='{request.state.access_level}'.")

    # --- Lógica de Autorização baseada nas permissões ---
    # Para rotas de soft-delete e restore, verifica a permissão 'can_delete_records'.
    if request.url.path.startswith("/api/v1/records/") and \
       ("soft-delete" in request.url.path or "restore" in request.url.path):
        if not request.state.can_delete_records:
            logger.warning(f"Middleware: Acesso negado para '{request.state.auth_app_name}'. Não possui permissão para deletar/restaurar registros em {request.url.path}.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para realizar esta operação."
            )
    
    # Prossegue para o próximo middleware ou para o endpoint da rota.
    response = await call_next(request)
    return response


### Modelos Pydantic para Requisições e Respostas

class UniversalValidationRequest(BaseModel):
    validation_type: str
    data: Dict[str, Any]
    client_identifier: Optional[str] = None
    operator_id: Optional[str] = None
    

class ValidationResponse(BaseModel):
    status: str
    message: str
    is_valid: bool
    validation_details: Dict[str, Any] # Uso Dict[str, Any] para clareza
    app_name: str 
    client_identifier: Optional[str] = None
    record_id: Optional[int] = None
    input_data_original: Optional[str] = None
    input_data_cleaned: Optional[str] = None
    regra_negocio_codigo: Optional[str] = None
    tipo_validacao: Optional[str] = None 
    origem_validacao: Optional[str] = None 
    regra_negocio_descricao: Optional[str] = None
    regra_negocio_tipo: Optional[str] = None
    regra_negocio_parametros: Optional[Dict[str, Any]] = None 

class HistoryRecordResponse(BaseModel):
    id: int
    dado_original: str
    dado_normalizado: Optional[str]
    is_valido: bool
    mensagem: str
    origem_validacao: str
    tipo_validacao: Optional[str]
    data_validacao: datetime
    app_name: Optional[str]
    client_identifier: Optional[str]
    regra_negocio_codigo: Optional[str]
    regra_negocio_descricao: Optional[str] = None 
    regra_negocio_tipo: Optional[str] = None 
    regra_negocio_parametros: Optional[Dict[str, Any]] = None 
    validation_details: Dict[str, Any]
    is_deleted: bool 
    deleted_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

class HistoryResponse(BaseModel):
    status: str
    data: List[HistoryRecordResponse]
    message: Optional[str] = None
    
# Função auxiliar para padronizar o tratamento de erros nos endpoints.
def _handle_service_response_error(result: Dict[str, Any]):
    """
    Auxilia no levantamento de HTTPException com base no dicionário de resultado do serviço.
    Extrai o código HTTP e a mensagem para uniformizar as respostas de erro da API.
    """
    status_code_from_result = result.get("code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    message = result.get("message", "Um erro inesperado ocorreu.")
    
    # Valida se o código HTTP retornado é um inteiro válido dentro do range HTTP.
    if not isinstance(status_code_from_result, int) or not (100 <= status_code_from_result < 600):
        status_code_from_result = status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.error(f"Código HTTP inválido retornado pelo serviço: {result.get('code')}. Usando 500 para {message}.")

    raise HTTPException(status_code=status_code_from_result, detail=message)

### Endpoints da API

@app.post(
    "/api/v1/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Valida dados de diversos tipos (telefone, endereço, etc.)",
    description="Recebe um tipo de validação (`phone`, `address`, `email`, `document`), os dados correspondentes, autentica a API Key e registra o resultado no banco de dados. Retorna o status da validação e detalhes."
)
async def validate_data_endpoint(
    request: Request,
    request_data: UniversalValidationRequest # Já é o seu objeto Pydantic
):
    """
    Realiza a validação de um dado específico através do ValidationService.
    """
    if val_service is None:
        logger.critical("ValidationService não inicializado no momento da requisição /api/v1/validate.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Serviço de validação não está pronto. Tente novamente mais tarde."
        )

    api_key_used = request.headers.get("x-api-key")

    # Chama o método assíncrono do ValidationService e aguarda seu resultado.
    result = await val_service.validate_data(
        api_key_str=api_key_used, # Passe como api_key_str (conforme a assinatura do método no serviço)
        request=request_data      # Passe o objeto UniversalValidationRequest completo
    )

    # Verifica o status retornado pelo serviço e levanta HTTPException se for um erro.
    if result.get("status") == "error": # Apenas 'error', não 'invalid'
        _handle_service_response_error(result)
    logger.info(f"Retornando ValidationResponse com dados: {result}") 
    # Retorna o resultado mapeado para o modelo de resposta Pydantic.
    return ValidationResponse(**result)



@app.get(
    "/api/v1/history",
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtém o histórico das últimas validações",
    description="Retorna uma lista dos últimos N registros de validação. Por padrão, não inclui registros deletados logicamente. Use `include_deleted=true` para visualizá-los."
)
async def get_history_endpoint(
    request: Request,
    limit: int = 5, 
    include_deleted: bool = False 
):
    """
    Obtém o histórico de validações registradas no sistema.
    """
    if val_service is None:
        logger.critical("ValidationService não inicializado no momento da requisição /api/v1/history.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Serviço de validação não está pronto. Tente novamente mais tarde."
        )

    # Chama o método assíncrono do ValidationService para obter o histórico.
    history_result = await val_service.get_validation_history(
        api_key=request.headers.get("x-api-key"),
        limit=limit,
        include_deleted=include_deleted
    )
    
    # Verifica o status do resultado e levanta HTTPException em caso de erro.
    if history_result.get("status") == "error":
        _handle_service_response_error(history_result)
    
    return HistoryResponse(**history_result)


@app.put(
    "/api/v1/records/{record_id}/soft-delete",
    status_code=status.HTTP_200_OK,
    summary="Deleta logicamente um registro de validação",
    description="Marca um registro de validação como 'deletado' sem removê-lo fisicamente do banco de dados. Requer autenticação por API Key (apenas para usuários MDM, via configuração de permissões na API Key)."
)
async def soft_delete_record_endpoint(
    request: Request,
    record_id: int
):
    """
    Marca um registro de validação como logicamente deletado.
    """
    if val_service is None:
        logger.critical("ValidationService não inicializado no momento da requisição /api/v1/records/{record_id}/soft-delete.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Serviço de validação não está pronto. Tente novamente mais tarde."
        )

    # Chama o método assíncrono para soft delete.
    result = await val_service.soft_delete_record(request.headers.get("x-api-key"), record_id)
    if result.get("status") in ["error", "failed"]:
        _handle_service_response_error(result)
    return {"message": result.get("message")}


@app.put(
    "/api/v1/records/{record_id}/restore",
    status_code=status.HTTP_200_OK,
    summary="Restaura um registro de validação deletado logicamente",
    description="Reverte a operação de soft delete para um registro, tornando-o ativo novamente. Requer autenticação por API Key (apenas para usuários MDM, via configuração de permissões na API Key)."
)
async def restore_record_endpoint(
    request: Request,
    record_id: int
):
    """
    Restaura um registro de validação que foi logicamente deletado.
    """
    if val_service is None:
        logger.critical("ValidationService não inicializado no momento da requisição /api/v1/records/{record_id}/restore.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Serviço de validação não está pronto. Tente novamente mais tarde."
        )

    # Chama o método assíncrono para restaurar o registro.
    result = await val_service.restore_record(request.headers.get("x-api-key"), record_id)
    if result.get("status") in ["error", "failed"]:
        _handle_service_response_error(result)
    return {"message": result.get("message")}


@app.get(
    "/health", 
    status_code=status.HTTP_200_OK,
    summary="Verifica a saúde da API",
    description="Retorna o status 'ok' se a API estiver funcionando corretamente e acessível."
)
async def health_check():
    """
    Endpoint para verificação de saúde da aplicação. Não requer autenticação.
    Verifica a conectividade do banco de dados para um status mais completo.
    """
    try:
        # Verifica se o DatabaseManager foi inicializado.
        if db_manager:
            # Tenta obter e liberar uma conexão para verificar a saúde do pool.
            conn = await db_manager.get_connection()
            await db_manager.put_connection(conn)
            db_status = "ok"
        else:
            db_status = "uninitialized"
        
        return {"status": "ok", "message": "API is running and healthy", "database_status": db_status}
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"API is unhealthy: {e}")