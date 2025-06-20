# app/config/settings.py

import os
import json
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../.env'),
        env_file_encoding='utf-8',
        extra='ignore'
    )

    DB_HOST: str = "localhost"
    DB_NAME: str = "Barramento" # Corrigido para "Barramento" conforme seu log
    DB_USER: str = "admin"
    DB_PASSWORD: str
    DB_PORT: int = 5432
    DB_POOL_MIN_CONN: int = 1
    DB_POOL_MAX_CONN: int = 10

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    _api_keys_cache: Optional[Dict[str, Any]] = None 

    @property
    def API_KEYS(self) -> Dict[str, Any]:
        if self._api_keys_cache is not None:
            logger.debug("API Keys retornadas do cache.")
            return self._api_keys_cache

        # Caminho para o arquivo api_keys.json
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
                logger.error(f"Erro ao carregar API Keys do arquivo {api_keys_path}: {e}. Isso pode ser o motivo do erro 'API Key inválida'. Verifique a sintaxe JSON do arquivo. Tentando carregar de variável de ambiente 'API_KEYS_JSON'.", exc_info=True)
        else:
            logger.warning(f"Arquivo de API Keys NÃO ENCONTRADO em: {api_keys_path}. Verifique o caminho. Tentando carregar de variável de ambiente 'API_KEYS_JSON'.")

        # Fallback para variável de ambiente
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
        self._api_keys_cache = {}
        return {}

    LOG_LEVEL: str = "INFO"

try:
    settings = Settings()
    logging.getLogger().setLevel(settings.LOG_LEVEL)
    logger.info("Configurações carregadas com sucesso do ambiente (incluindo .env se presente).")
except ValidationError as e:
    logger.critical(f"Erro de validação nas configurações: {e.errors()}. A aplicação não pode iniciar.", exc_info=True)
    raise
except Exception as e:
    logger.critical(f"Erro inesperado ao carregar configurações: {e}. A aplicação não pode iniciar.", exc_info=True)
    raise
