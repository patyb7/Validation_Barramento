import os
import json
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import ValidationError, Field
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
    DB_NAME: str = "Barramento_Full"
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

    API_KEYS_JSON: str = Field(
        default_factory=lambda: json.dumps({
            "API_KEY_SEGUROS": {
                "app_name": "Seguros App",
                "permissions": ["read", "write"],
                "can_delete_records": False,
                "can_check_duplicates": False,
                "can_request_enrichment": False # NOVO: Permissão padrão
            },
            "API_KEY_FINANCAS": {
                "app_name": "Financas App",
                "permissions": ["read"],
                "can_delete_records": True,
                "access_level": "admin",
                "can_check_duplicates": True,
                "can_request_enrichment": False # NOVO: Permissão padrão
            },
            "API_KEY_ADMIN": {
                "app_name": "Admin Console",
                "permissions": ["read", "write", "delete"],
                "can_delete_records": True,
                "access_level": "superadmin",
                "can_check_duplicates": True,
                "can_request_enrichment": True # NOVO: Permissão padrão
            }
        }),
        env="API_KEYS_JSON"
    )

    @property
    def API_KEYS(self) -> Dict[str, Any]:
        try:
            keys = json.loads(self.API_KEYS_JSON)
            if not isinstance(keys, dict):
                raise ValueError("API_KEYS_JSON deve ser um objeto JSON que representa um dicionário.")
            return keys
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Erro ao carregar API_KEYS_JSON: {e}. Certifique-se de que é um JSON válido. Usando dicionário vazio.", exc_info=True)
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