# app/auth/api_key_manager.py
import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class APIKeyManager:
    """
    Gerencia o carregamento e a validação das API Keys.
    Carrega as chaves de um arquivo JSON.
    """
    _instance: Optional['APIKeyManager'] = None
    _is_initialized: bool = False

    def __new__(cls, *args, **kwargs):
        """Implementa o padrão Singleton para APIKeyManager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, api_keys_file: str = "app/config/api_keys.json"):
        """
        Inicializa o APIKeyManager. Carrega as API Keys do arquivo especificado.
        Garanto que a inicialização só ocorre uma vez por instância Singleton.
        """
        if not self._is_initialized:
            self.api_keys_file = api_keys_file
            self.api_keys: Dict[str, Dict[str, Any]] = {}
            self._load_api_keys()
            self._is_initialized = True
            logger.info("APIKeyManager inicializado.")
        else:
            logger.debug("APIKeyManager já inicializado. Pulando re-inicialização.")


    def _load_api_keys(self) -> None:
        """
        Carrega as API Keys do arquivo JSON especificado.
        Se o arquivo não for encontrado ou houver um erro de parsing, as chaves não serão carregadas.
        """
        if not os.path.exists(self.api_keys_file):
            logger.error(f"Arquivo de API Keys não encontrado: {self.api_keys_file}")
            self.api_keys = {}
            return

        try:
            with open(self.api_keys_file, 'r', encoding='utf-8') as f:
                self.api_keys = json.load(f)
            logger.info(f"API Keys carregadas com sucesso do arquivo: {self.api_keys_file}: {len(self.api_keys)} chaves.")
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON do arquivo de API Keys '{self.api_keys_file}': {e}")
            self.api_keys = {}
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar API Keys do arquivo '{self.api_keys_file}': {e}", exc_info=True)
            self.api_keys = {}

    def get_app_info(self, api_key_str: str) -> Optional[Dict[str, Any]]:
        """
        Retorna as informações da aplicação associadas a uma API Key, se a chave for válida e ativa.
        """
        app_info = self.api_keys.get(api_key_str)
        if app_info and app_info.get("is_active", False):
            logger.debug(f"Informações da aplicação para API Key '{api_key_str[:5]}...' encontradas e ativas: {app_info.get('app_name')}")
            return app_info
        
        if app_info and not app_info.get("is_active", False):
            logger.warning(f"Tentativa de usar API Key '{api_key_str[:5]}...' inativa. App: {app_info.get('app_name')}")
        else:
            logger.warning(f"API Key '{api_key_str[:5]}...' não encontrada ou inválida.")
        
        return None

    def authenticate_request(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Autentica uma requisição usando a API Key fornecida nos headers.
        Retorna um dicionário com o status de autenticação e as informações da aplicação, se autenticado.
        """
        api_key_str = headers.get("x-api-key")
        
        if not api_key_str:
            logger.warning("Tentativa de acesso sem API Key no cabeçalho 'X-API-Key'.")
            return {"authenticated": False, "message": "API Key ausente."}

        app_info = self.get_app_info(api_key_str)
        
        if app_info:
            logger.info(f"API Key '{api_key_str[:5]}...' autenticada para a aplicação '{app_info.get('app_name', 'Desconhecido')}'.")
            return {"authenticated": True, "app_info": app_info, "message": "Autenticação bem-sucedida."}
        else:
            logger.warning(f"Falha na autenticação para API Key '{api_key_str[:5]}...': Inválida ou inativa.")
            return {"authenticated": False, "message": "API Key inválida ou não autorizada."}

    def reload_api_keys(self) -> None:
        """Recarrega as API Keys do arquivo. Útil para atualizações em tempo de execução."""
        logger.info("Recarregando API Keys...")
        self._load_api_keys()
