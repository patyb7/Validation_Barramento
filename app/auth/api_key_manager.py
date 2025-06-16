# app/auth/api_key_manager.py

from typing import Dict, Any, Optional
from app.config.settings import settings # Importa a instância global das configurações

class APIKeyManager:
    """
    Gerencia a autenticação de requisições através de API Keys.
    Valida a API Key fornecida nos headers da requisição contra
    um conjunto de chaves pré-configuradas, retornando os metadados
    da aplicação associada.
    """

    @classmethod
    def _get_api_key_from_headers(cls, headers: Dict[str, str]) -> Optional[str]:
        """
        Extrai a API Key dos headers da requisição, procurando por "X-API-Key"
        de forma case-insensitive.
        """
        for key, value in headers.items():
            if key.lower() == "x-api-key":
                return value
        return None

    @classmethod
    def authenticate_request(cls, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Autentica uma requisição verificando a API Key presente nos headers.

        Args:
            headers: Dicionário contendo os cabeçalhos da requisição HTTP.

        Returns:
            Um dicionário com o resultado da autenticação:
            - "authenticated": True se a chave for válida, False caso contrário.
            - "message": Mensagem de status ou erro.
            - "app_info": (Opcional) Dicionário com metadados da aplicação associada à chave,
                          se a autenticação for bem-sucedida.
        """
        api_key = cls._get_api_key_from_headers(headers)

        if not api_key:
            return {"authenticated": False, "message": "API Key não fornecida no cabeçalho 'X-API-Key'."}
        
        # Acessa as API Keys configuradas via o objeto settings
        app_info = settings.API_KEYS.get(api_key)

        if app_info:
            # Você pode adicionar mais verificações aqui se quiser,
            # por exemplo, para verificar se a API Key está ativa, expirada, etc.
            return {"authenticated": True, "app_info": app_info}
        else:
            # Evita dar muitas informações sobre por que a chave falhou (segurança)
            return {"authenticated": False, "message": "API Key inválida ou não reconhecida."}