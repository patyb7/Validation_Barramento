# app/auth/api_key_manager.py

import logging # Importa o módulo logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__) # Obtém o logger para este módulo

class APIKeyManager:
    """
    Gerencia a autenticação de requisições através de API Keys.
    Valida a API Key fornecida nos headers da requisição contra
    um conjunto de chaves pré-configuradas, retornando os metadados
    da aplicação associada.
    """
    def __init__(self, api_keys: Dict[str, Any]):
        """
        Inicializa o APIKeyManager com um dicionário de API Keys.
        No futuro, esta classe pode ser estendida para carregar chaves de um Vault.
        """
        self.api_keys = api_keys
        # Substituído 'print' por 'logger.debug' para padronizar o logging
        logger.debug(f"APIKeyManager: Inicializado com {len(self.api_keys)} API Keys.") 

    def _get_api_key_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        logger.debug(f"API Key recebida na função de autenticação: '{x_api_key}'")
        """
        Extrai a API Key dos headers da requisição, procurando por "X-API-Key"
        de forma case-insensitive.
        """
        for key, value in headers.items():
            if key.lower() == "x-api-key":
                logger.debug(f"API Key 'X-API-Key' encontrada nos headers: '{value}'")
                return value
        logger.debug("API Key 'X-API-Key' não encontrada nos headers.")
        logger.warning("Nenhuma API Key encontrada nos headers da requisição.")
        return None

    def get_app_info(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Retorna as informações da aplicação associada a uma API Key, se válida.
        Este método é usado pelo ValidationService.
        """
        # Loga a tentativa de busca da app_info para a API Key fornecida
        logger.debug(f"Tentando obter informações da aplicação para a API Key: '{api_key}'")
        app_info = self.api_keys.get(api_key)
        if app_info:
            logger.debug(f"Informações da aplicação encontradas para a API Key: {app_info.get('app_name')}")
        else:
            logger.debug(f"Nenhuma informação de aplicação encontrada para a API Key: '{api_key}'")
        return self.api_keys.get(api_key)

    def authenticate_request(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Autentica uma requisição verificando a API Key presente nos headers.
        """
        logger.debug("Iniciando autenticação da requisição.")
        api_key = self._get_api_key_from_headers(headers)

        if not api_key:
            logger.warning("Autenticação falhou: API Key não fornecida.")
            return {"authenticated": False, "message": "API Key não fornecida no cabeçalho 'X-API-Key'."}
        
        app_info = self.get_app_info(api_key)

        if app_info:
            logger.info(f"Autenticação bem-sucedida para a aplicação: {app_info.get('app_name')}")
            return {"authenticated": True, "app_info": app_info}
        else:
            logger.warning(f"Autenticação falhou: API Key '{api_key}' inválida ou não reconhecida.")
            return {"authenticated": False, "message": "API Key inválida ou não reconhecida."}
