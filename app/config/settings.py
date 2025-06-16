# app/config/settings.py

import os
import json
import logging
from dotenv import load_dotenv, find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import ValidationError
from typing import Dict, Any, Optional

# Importar as bibliotecas do Azure Key Vault
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import ResourceNotFoundError, ClientAuthenticationError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Carregamento de variáveis de ambiente do .env (para desenvolvimento local) ---
dotenv_path = find_dotenv()
if dotenv_path:
    logger.info(f"DEBUG: Arquivo .env encontrado em: {dotenv_path}")
    load_dotenv(dotenv_path) # Carrega as variáveis do .env no ambiente
else:
    logger.warning("DEBUG: Arquivo .env não encontrado. Tentando carregar de variáveis de ambiente ou Azure Key Vault.")

# --- Configurações da aplicação ---
class AppSettings(BaseSettings):
    """
    Configurações da aplicação e do banco de dados, carregadas de variáveis de ambiente.
    Pode carregar do .env ou, em produção, do Azure Key Vault.
    """
    model_config = SettingsConfigDict(
        env_file=".env", # Ainda pode ser usado como fallback ou para hints de Pydantic
        env_file_encoding="utf-8",
        case_sensitive=True,
        # Se você quiser que o Pydantic ignore campos que não estão definidos na classe,
        # mas que existem no .env ou Key Vault, você pode usar 'extra_forbidden'.
        # Por padrão, Pydantic v2+ já faz isso. Se quiser permitir extras, use 'extra="allow"'
    )

    # --- Configurações do Banco de Dados ---
    DB_HOST: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    DB_PORT: int = 5432

    # --- Configurações de Logging ---
    LOG_LEVEL: str = "INFO"

    # --- Configurações de API Keys ---
    API_KEYS_SYSTEMS: str # Será uma string JSON vinda do KV ou .env

    # --- Configuração do Azure Key Vault ---
    # Optional[str] significa que pode ser None se não estiver definido
    # Isso permite que a aplicação funcione sem Key Vault em dev local, por exemplo
    AZURE_KEY_VAULT_NAME: Optional[str] = None # Nome do seu Key Vault, e.g., "MeuKeyVault"

    @property
    def API_KEYS(self) -> Dict[str, Dict[str, Any]]:
        """
        Retorna as API Keys e seus metadados como um dicionário Python.
        Faz o parse da string JSON de API_KEYS_SYSTEMS.
        """
        try:
            parsed_keys = json.loads(self.API_KEYS_SYSTEMS)
            if not isinstance(parsed_keys, dict):
                raise ValueError("API_KEYS_SYSTEMS deve ser um JSON que representa um dicionário.")
            return parsed_keys
        except json.JSONDecodeError as e:
            logger.critical(f"ERRO DE CONFIGURAÇÃO FATAL: Variável de ambiente API_KEYS_SYSTEMS não é um JSON válido. Detalhe: {e}")
            raise ValueError("Configuração inválida para API_KEYS_SYSTEMS. Não é um JSON válido.") from e
        except ValueError as e:
            logger.critical(f"ERRO DE CONFIGURAÇÃO FATAL: {e}")
            raise

# --- Instância global das configurações ---
# A lógica de carregamento do Key Vault será encapsulada aqui
_settings_instance: Optional[AppSettings] = None

def get_settings() -> AppSettings:
    """
    Retorna a instância singleton das configurações.
    Tenta carregar do Key Vault se AZURE_KEY_VAULT_NAME estiver definido
    e as variáveis não estiverem no ambiente.
    """
    global _settings_instance
    if _settings_instance is None:
        try:
            # Tenta carregar do ambiente (incluindo .env já carregado)
            _settings_instance = AppSettings()
            logger.info("Configurações carregadas com sucesso do ambiente.")

        except ValidationError as e_env:
            logger.warning(f"Erro de validação inicial do ambiente: {e_env.errors()}")
            # Se falhar no ambiente, e AZURE_KEY_VAULT_NAME estiver definido, tenta o Key Vault
            key_vault_name = os.getenv("AZURE_KEY_VAULT_NAME")
            if key_vault_name:
                logger.info(f"Tentando carregar segredos do Azure Key Vault: {key_vault_name}")
                key_vault_uri = f"https://{key_vault_name}.vault.azure.net/"
                try:
                    credential = DefaultAzureCredential()
                    secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)

                    # Recupera os segredos do Key Vault
                    kv_secrets = {}
                    kv_secrets["DB_HOST"] = secret_client.get_secret("DB-HOST").value
                    kv_secrets["DB_NAME"] = secret_client.get_secret("DB-NAME").value
                    kv_secrets["DB_USER"] = secret_client.get_secret("DB-USER").value
                    kv_secrets["DB_PASSWORD"] = secret_client.get_secret("DB-PASSWORD").value
                    kv_secrets["DB_PORT"] = secret_client.get_secret("DB-PORT").value # Valor já é string, Pydantic converterá para int
                    kv_secrets["API_KEYS_SYSTEMS"] = secret_client.get_secret("API-KEYS-SYSTEMS").value
                    # Você também pode buscar LOG_LEVEL se o tiver no KV
                    # kv_secrets["LOG_LEVEL"] = secret_client.get_secret("LOG-LEVEL").value

                    # Cria uma nova instância de AppSettings com os valores do Key Vault
                    _settings_instance = AppSettings(**kv_secrets)
                    logger.info("Configurações carregadas com sucesso do Azure Key Vault.")

                except (ClientAuthenticationError, ResourceNotFoundError) as e_kv:
                    logger.critical(f"ERRO DE AUTENTICAÇÃO/RECURSO AO ACESSAR KEY VAULT: {e_kv}. Verifique permissões e nome do Key Vault.")
                    # Se falhou autenticando ou encontrando o recurso, levanta o erro original do Pydantic
                    raise e_env from e_kv # Re-levanta o erro de validação original se o KV também falhar
                except Exception as e_kv_general:
                    logger.critical(f"ERRO INESPERADO ao carregar do Key Vault: {e_kv_general}")
                    raise e_env from e_kv_general # Re-levanta o erro de validação original

            else:
                logger.critical("ERRO DE VALIDAÇÃO DE CONFIGURAÇÃO: As variáveis de ambiente necessárias não foram fornecidas ou estão inválidas, e AZURE_KEY_VAULT_NAME não está definido para fallback. Detalhe:")
                logger.critical(e_env.errors())
                exit(1) # Sair se não puder carregar as configurações obrigatórias

        except Exception as e:
            logger.critical(f"ERRO INESPERADO ao carregar configurações: {e}")
            exit(1)
    return _settings_instance

# A instância global `settings` agora é uma chamada de função
# Isso garante que a lógica de fallback para Key Vault seja executada
settings = get_settings()