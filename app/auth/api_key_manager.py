# app/auth/api_key_manager.py

from typing import Dict, Any, Optional

class APIKeyManager:
    """
    Gerencia a autenticação de requisições através de API Keys.
    Valida a API Key fornecida nos headers da requisição contra
    um conjunto de chaves pré-configuradas, retornando os metadados
    da aplicação associada.
    """
    def __init__(self, api_keys: Dict[str, Any]): # Mantenha o construtor
        """
        Inicializa o APIKeyManager com um dicionário de API Keys.
        No futuro, esta classe pode ser estendida para carregar chaves de um Vault.
        """
        self.api_keys = api_keys
        print(f"DEBUG APIKeyManager: Inicializado com {len(self.api_keys)} API Keys.")

    def _get_api_key_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Extrai a API Key dos headers da requisição, procurando por "X-API-Key"
        de forma case-insensitive.
        """
        for key, value in headers.items():
            if key.lower() == "x-api-key":
                return value
        return None

    def get_app_info(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Retorna as informações da aplicação associada a uma API Key, se válida.
        Este método é usado pelo ValidationService.
        """
        return self.api_keys.get(api_key)

    def authenticate_request(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Autentica uma requisição verificando a API Key presente nos headers.
        """
        api_key = self._get_api_key_from_headers(headers)

        if not api_key:
            return {"authenticated": False, "message": "API Key não fornecida no cabeçalho 'X-API-Key'."}
        
        # Agora chama o método get_app_info que foi adicionado
        app_info = self.get_app_info(api_key)

        if app_info:
            return {"authenticated": True, "app_info": app_info}
        else:
            return {"authenticated": False, "message": "API Key inválida ou não reconhecida."}