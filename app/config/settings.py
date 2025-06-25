# app/config/settings.py

import os
import json
import logging
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any, Optional
from pathlib import Path

# Importar ValidationError para tratamento de erros
from pydantic import ValidationError

logger = logging.getLogger(__name__)

# Configuração inicial de logging para o módulo de settings, se ainda não houver handlers
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Determina a raiz do projeto dinamicamente.
# "__file__" aponta para o próprio arquivo settings.py (ex: .../Validation_Barramento/app/config/settings.py)
# .resolve() obtém o caminho absoluto.
# .parent (uma vez) -> .../Validation_Barramento/app/config/
# .parent.parent -> .../Validation_Barramento/app/
# .parent.parent.parent -> .../Validation_Barramento/ (Esta é a raiz do seu projeto)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    """
    Classe de configurações para a aplicação, carregando de variáveis de ambiente e .env.
    Inclui configurações de banco de dados e lógica robusta para API Keys.
    """
    model_config = SettingsConfigDict(
        # Define o caminho do arquivo .env relativo à raiz do projeto
        env_file=PROJECT_ROOT / ".env",
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

    # --- Configuração do Caminho ABSOLUTO para o Arquivo de API Keys ---
    # Constrói o caminho para 'api_keys.json' a partir da raiz do projeto.
    # O APIKeyManager receberá este caminho absoluto, garantindo que o arquivo seja encontrado.
    API_KEYS_FILE: Path = PROJECT_ROOT / "app" / "config" / "api_keys.json"

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

    # Adiciona um log de verificação para o caminho do arquivo API Keys
    if settings.API_KEYS_FILE.exists():
        logger.info(f"Configurações: Caminho do arquivo API Keys resolvido para: {settings.API_KEYS_FILE} e EXISTE.")
    else:
        logger.error(f"Configurações: Caminho do arquivo API Keys resolvido para: {settings.API_KEYS_FILE} mas NÃO EXISTE. Verifique a estrutura de pastas.")
    logger.info("Configurações carregadas com sucesso do ambiente (incluindo .env se presente).")
except ValidationError as e:
    logger.critical(f"Erro de validação nas configurações: {e.errors()}. A aplicação não pode iniciar.", exc_info=True)
    raise
except Exception as e:
    logger.critical(f"Erro inesperado ao carregar configurações: {e}. A aplicação não pode iniciar.", exc_info=True)
    raise
