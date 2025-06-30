from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseValidator(ABC):
    """
    Classe base abstrata para todos os validadores de dados.
    Define a interface comum para métodos de validação.
    """
    def __init__(self, origin_name: str, db_manager: Optional[Any] = None):
        # O nome da origem do validador (ex: "phone_validator", "email_validator")
        self.origin_name = origin_name
        # O gerenciador de banco de dados, opcional. Útil para validadores que precisam de dados externos.
        self.db_manager = db_manager 

    @abstractmethod
    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Método abstrato para validar um dado específico.
        Deve retornar um dicionário com o resultado da validação.

        Args:
            data (Any): O dado a ser validado.
            **kwargs: Argumentos adicionais específicos para a validação (ex: country_code_hint).

        Returns:
            Dict[str, Any]: Um dicionário padronizado com o resultado da validação.
                            Ex: {"is_valid": True, "dado_normalizado": "...", "mensagem": "..."}
        """
        pass
        
    def _format_result(self, is_valid: bool, dado_normalizado: Optional[str], mensagem: str, details: Dict[str, Any], business_rule_applied: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Formata um resultado de validação de forma consistente.

        Args:
            is_valid (bool): Indica se o dado é válido.
            dado_normalizado (Optional[str]): A versão normalizada do dado, se aplicável.
            mensagem (str): Uma mensagem descritiva do resultado da validação.
            details (Dict[str, Any]): Um dicionário com detalhes adicionais específicos da validação.
            business_rule_applied (Optional[Dict[str, Any]]): Detalhes da regra de negócio que determinou o resultado.

        Returns:
            Dict[str, Any]: O dicionário de resultado formatado.
        """
        result = {
            "is_valid": is_valid,
            "dado_normalizado": dado_normalizado,
            "mensagem": mensagem,
            "origem_validacao": self.origin_name,
            "details": details
        }
        if business_rule_applied:
            result["business_rule_applied"] = business_rule_applied
        return result