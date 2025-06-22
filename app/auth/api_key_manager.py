# app/auth/api_key_manager.py
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class APIKeyManager:
    """
    Gerencia as chaves de API para autenticação de requisições.
    Carrega as chaves de um arquivo JSON e as disponibiliza para validação.
    """
    _instance = None # Singleton pattern
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(APIKeyManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, api_keys_file_path: str = "app/config/api_keys.json"):
        if not self._initialized:
            self.api_keys: Dict[str, Dict[str, Any]] = {}
            self.api_keys_file_path = api_keys_file_path
            self._load_api_keys()
            self._initialized = True
            logger.info(f"API Keys carregadas com sucesso: {len(self.api_keys)} chaves.")

    def _load_api_keys(self):
        """Carrega as API Keys de um arquivo JSON."""
        try:
            with open(self.api_keys_file_path, 'r', encoding='utf-8') as f:
                self.api_keys = json.load(f)
            logger.info(f"Tentando carregar API Keys do arquivo: {self.api_keys_file_path}")
        except FileNotFoundError:
            logger.error(f"Arquivo de API Keys não encontrado: {self.api_keys_file_path}")
            self.api_keys = {}
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON do arquivo de API Keys '{self.api_keys_file_path}': {e}")
            self.api_keys = {}
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar API Keys: {e}")
            self.api_keys = {}

    def _get_api_key_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """Extrai a API Key dos cabeçalhos da requisição."""
        # CORREÇÃO: Atribua o valor do cabeçalho a x_api_key antes de usá-lo no log
        x_api_key = headers.get("Sistema de PSDC")
        logger.debug(f"API Key recebida na função de autenticação: '{x_api_key}'")
        return x_api_key

    def authenticate_request(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Autentica uma requisição HTTP verificando a API Key nos cabeçalhos.
        Retorna um dicionário com o status da autenticação e as informações da aplicação.
        """
        api_key = self._get_api_key_from_headers(headers)

        if not api_key:
            return {"authenticated": False, "reason": "API Key ausente."}

        app_info = self.api_keys.get(api_key)

        if app_info:
            logger.info(f"API Key '{api_key[:5]}...' autenticada para a aplicação '{app_info.get('app_name', 'Desconhecida')}'.")
            return {"authenticated": True, "app_info": app_info}
        else:
            logger.warning(f"Tentativa de autenticação com API Key inválida: {api_key[:5]}...")
            return {"authenticated": False, "reason": "API Key inválida."}

    def get_app_info(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Retorna as informações da aplicação associada a uma API Key."""
        return self.api_keys.get(api_key)

