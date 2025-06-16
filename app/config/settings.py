# app/config/settings.py

import os
import json
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import ValidationError
from typing import Dict, Any, Optional

# --- FORÇAR A SENHA 'admin' DIRETAMENTE NO AMBIENTE (para DEBUG local) ---
# Esta linha pode ser removida ou comentada em produção, se a senha
# for definida por variáveis de ambiente do sistema operacional ou .env
# REMOVA OU COMENTE ISSO EM PRODUÇÃO. É uma medida de segurança ruim.
os.environ["DB_PASSWORD"] = "admin"
print(f"DEBUG INICIAL SETTINGS.PY: os.environ['DB_PASSWORD'] forçado para: '{os.environ['DB_PASSWORD']}'")
print(f"DEBUG INICIAL SETTINGS.PY: os.environ['DB_PASSWORD'] forçado em HEX: {os.environ['DB_PASSWORD'].encode('utf-8').hex()}")
# --- FIM DA FORÇAÇÃO ---

# Configuração de logging.
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class Settings(BaseSettings):
    # Configuração para carregar variáveis de ambiente de um arquivo .env
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../.env'),
        env_file_encoding='utf-8',
        extra='ignore' # Ignora variáveis no .env que não estão no modelo
    )

    # Configurações do Banco de Dados PostgreSQL
    DB_HOST: str = "localhost"
    DB_NAME: str = "prototipo"
    DB_USER: str = "admin"
    DB_PASSWORD: str # Esta variável será lida do ambiente/arquivo .env
    DB_PORT: int = 5432
    DB_POOL_MIN_CONN: int = 1
    DB_POOL_MAX_CONN: int = 10

    # Adicionando a propriedade computada DATABASE_URL
    @property
    def DATABASE_URL(self) -> str:
        """
        Monta a URL de conexão do banco de dados a partir das configurações.
        """
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # Chaves de API para autenticação de clientes
    # Exemplo: {"API_KEY_SEGUROS": {"app_name": "Seguros App", "permissions": ["read", "write"]}, ...}
    # ATENÇÃO: Em produção, estas chaves devem ser gerenciadas de forma mais segura (ex: HashiCorp Vault)
    # Por enquanto, carregamos de uma variável de ambiente JSON ou de um valor padrão.
    API_KEYS_JSON: str = os.getenv(
        "API_KEYS_JSON", # Tenta carregar de uma variável de ambiente
        json.dumps({ # Valor padrão se a variável de ambiente não existir
            "API_KEY_SEGUROS": {"app_name": "Seguros App", "permissions": ["read", "write"]},
            "API_KEY_FINANCAS": {"app_name": "Financas App", "permissions": ["read"]},
            "API_KEY_ADMIN": {"app_name": "Admin Console", "permissions": ["read", "write", "delete"]}
        })
    )

    # Propriedade computada para retornar as API Keys como um dicionário
    @property
    def API_KEYS(self) -> Dict[str, Any]:
        try:
            keys = json.loads(self.API_KEYS_JSON)
            if not isinstance(keys, dict):
                raise ValueError("API_KEYS_JSON deve ser um objeto JSON que representa um dicionário.")
            return keys
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Erro ao carregar API_KEYS_JSON: {e}. Usando dicionário vazio.")
            return {}

    # Configurações de logging
    LOG_LEVEL: str = "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Cria uma instância única das configurações para ser importada em outros módulos
try:
    settings = Settings()
    logging.getLogger().setLevel(settings.LOG_LEVEL) # Aplica o nível de log globalmente
    logger.info("Configurações carregadas com sucesso do ambiente (incluindo .env se presente).")
except ValidationError as e:
    logger.error(f"Erro de validação nas configurações: {e.errors()}")
    raise
except Exception as e:
    logger.error(f"Erro inesperado ao carregar configurações: {e}")
    raise