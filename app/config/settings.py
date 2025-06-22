# app/config/settings.py

import os
import json
import logging
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any, Optional

# Importar ValidationError para tratamento de erros
from pydantic import ValidationError

logger = logging.getLogger(__name__)

# Configuração inicial de logging para o módulo de settings, se ainda não houver handlers
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class Settings(BaseSettings):
    """
    Classe de configurações para a aplicação, carregando de variáveis de ambiente e .env.
    Inclui configurações de banco de dados e lógica robusta para API Keys.
    """
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../.env'),
        env_file_encoding='utf-8',
        extra='ignore' # Ignora chaves no .env que não estão definidas no modelo
    )

    APP_NAME: str = "BarramentoDeValidacao"
    API_V1_STR: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    # --- Configurações Detalhadas do Banco de Dados ---
    DB_HOST: str = "localhost"
    DB_NAME: str = "Barramento" 
    DB_USER: str = "admin"
    DB_PASSWORD: str # Será lido do .env ou ambiente
    DB_PORT: int = 5432
    DB_POOL_MIN_CONN: int = 1
    DB_POOL_MAX_CONN: int = 10

    @property
    def DATABASE_URL(self) -> str:
        """Constrói a URL de conexão com o banco de dados a partir das configurações."""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # --- Configuração do Caminho para o Arquivo de API Keys ---
    # Este é o caminho padrão que o APIKeyManager espera
    API_KEYS_FILE: str = "app/config/api_keys.json" 

    # --- Lógica Robusta para Carregamento de API Keys (com cache e fallback) ---
    _api_keys_cache: Optional[Dict[str, Any]] = None 

    @property
    def API_KEYS(self) -> Dict[str, Any]:
        """
        Carrega as API Keys de um arquivo JSON ou de uma variável de ambiente,
        com caching para evitar leituras repetidas.
        """
        if self._api_keys_cache is not None:
            logger.debug("API Keys retornadas do cache.")
            return self._api_keys_cache

        # Tenta carregar do arquivo
        api_keys_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api_keys.json')
        logger.info(f"Tentando carregar API Keys do arquivo: {api_keys_path}")
        
        if os.path.exists(api_keys_path):
            try:
                with open(api_keys_path, 'r', encoding='utf-8') as f:
                    keys = json.load(f)
                    if not isinstance(keys, dict):
                        raise ValueError("Conteúdo de api_keys.json deve ser um objeto JSON.")
                    logger.info(f"API Keys carregadas com sucesso do arquivo: {len(keys)} chaves.")
                    self._api_keys_cache = keys
                    return keys
            except (json.JSONDecodeError, IOError, ValueError) as e:
                logger.error(f"Erro ao carregar API Keys do arquivo {api_keys_path}: {e}. Tentando carregar de variável de ambiente 'API_KEYS_JSON'.", exc_info=True)
        else:
            logger.warning(f"Arquivo de API Keys NÃO ENCONTRADO em: {api_keys_path}. Verifique o caminho. Tentando carregar de variável de ambiente 'API_KEYS_JSON'.")

        # Fallback para variável de ambiente 'API_KEYS_JSON'
        api_keys_json_from_env = os.getenv("API_KEYS_JSON")
        if api_keys_json_from_env:
            try:
                keys = json.loads(api_keys_json_from_env)
                if not isinstance(keys, dict):
                    raise ValueError("API_KEYS_JSON (env var) deve ser um objeto JSON.")
                logger.info(f"API Keys carregadas com sucesso da variável de ambiente 'API_KEYS_JSON': {len(keys)} chaves.")
                self._api_keys_cache = keys
                return keys
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Erro ao carregar API_KEYS_JSON da variável de ambiente: {e}. Usando dicionário vazio.", exc_info=True)
        
        logger.critical("Nenhuma API Key carregada com sucesso, nem de arquivo, nem de variável de ambiente. Isso pode levar a erros de autenticação.")
        self._api_keys_cache = {} # Garante que o cache é definido para evitar repetições
        return {}

    # --- Propriedade para obter o nível de log numérico ---
    @property
    def get_log_level(self) -> int:
        """Converte a string do nível de log para o valor numérico correspondente."""
        level_map = {
            "CRITICAL": logging.CRITICAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
            "NOTSET": logging.NOTSET
        }
        return level_map.get(self.LOG_LEVEL.upper(), logging.INFO)

# Caching da instância de configurações para evitar recarregar desnecessariamente
@lru_cache()
def get_settings():
    """Retorna uma instância singleton das configurações da aplicação."""
    return Settings()

try:
    settings = get_settings() # Carrega as configurações na inicialização do módulo
    logging.getLogger().setLevel(settings.get_log_level) # Usa o método get_log_level
    logger.info("Configurações carregadas com sucesso do ambiente (incluindo .env se presente).")
except ValidationError as e:
    logger.critical(f"Erro de validação nas configurações: {e.errors()}. A aplicação não pode iniciar.", exc_info=True)
    raise
except Exception as e:
    logger.critical(f"Erro inesperado ao carregar configurações: {e}. A aplicação não pode iniciar.", exc_info=True)
    raise
