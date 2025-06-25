# app/auth/api_key_manager.py
import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class APIKeyManager:
    """
    Gerencia as chaves de API, incluindo carregamento, validação e verificação de permissões.
    """
    def __init__(self, api_keys_file: str):
        """
        Inicializa o gerenciador de chaves de API.
        Args:
            api_keys_file (str): Caminho para o arquivo JSON contendo as chaves de API.
        """
        self.api_keys_file = api_keys_file
        self._api_keys: Dict[str, Dict[str, Any]] = {}
        self._load_api_keys()
        logger.info("APIKeyManager inicializado.")

    def _load_api_keys(self):
        """
        Carrega as chaves de API do arquivo JSON especificado.
        """
        logger.info(f"Tentando carregar API Keys do arquivo: {self.api_keys_file}")
        if not os.path.exists(self.api_keys_file):
            logger.error(f"Arquivo de API Keys não encontrado: {self.api_keys_file}")
            self._api_keys = {} # Garante que _api_keys está vazio se o arquivo não for encontrado
            return

        try:
            with open(self.api_keys_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    logger.error(f"Conteúdo do arquivo {self.api_keys_file} não é um dicionário JSON válido.")
                    self._api_keys = {}
                    return

                self._api_keys = data
                logger.info(f"API Keys carregadas com sucesso do arquivo: {len(self._api_keys)} chaves.")
                # NOVO LOG: Mostra as chaves carregadas (apenas os nomes das chaves para segurança)
                for key, details in self._api_keys.items():
                    logger.debug(f"Carregada chave: '{key}' com detalhes: {details.get('app_name', 'N/A')}, is_active: {details.get('is_active', False)}")

        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON do arquivo {self.api_keys_file}: {e}")
            self._api_keys = {}
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar API Keys do arquivo {self.api_keys_file}: {e}")
            self._api_keys = {}

    def get_app_info(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Retorna as informações da aplicação associada a uma API Key, se for válida e ativa.
        Args:
            api_key (str): A chave de API fornecida na requisição.
        Returns:
            Optional[Dict[str, Any]]: Um dicionário com as informações da aplicação
                                      (app_name, permissões, etc.) ou None se a chave for inválida.
        """
        # NOVO LOG: Mostra a API Key que está sendo procurada (primeiros caracteres)
        logger.debug(f"Procurando por API Key: '{api_key[:8]}...'")

        app_info = self._api_keys.get(api_key)
        
        if app_info and app_info.get("is_active"):
            logger.info(f"API Key '{api_key[:8]}...' (App: {app_info.get('app_name', 'Desconhecido')}) encontrada e ativa.")
            return app_info
        
        logger.warning(f"API Key '{api_key[:8]}...' não encontrada ou inválida.")
        return None

