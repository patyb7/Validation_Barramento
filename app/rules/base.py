import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

class BaseValidator:
    """
    Classe base abstrata para todos os validadores no barramento.
    Define a interface comum e o método para formatar os resultados de validação.
    """
    def __init__(self, origin_name: str):
        """
        Inicializa o BaseValidator.
        Args:
            origin_name (str): O nome da origem específica deste validador (ex: "cpf_validator", "cep_validator").
        """
        self.origin_name = origin_name
        self.VAL_GENERIC_EMPTY = "VAL_GENERIC_001" # Código para input vazio ou tipo inválido
        self.VAL_GENERIC_VALID = "VAL_GENERIC_002" # Código para input válido
        self.VAL_GENERIC_INVALID = "VAL_GENERIC_003" # Código para input inválido
        logger.info(f"BaseValidator '{self.origin_name}' inicializado.")

    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Método abstrato para validação. Deve ser implementado por subclasses.
        Args:
            data (Any): O dado a ser validado.
            **kwargs: Argumentos adicionais específicos do validador.
        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação.
        """
        raise NotImplementedError("O método 'validate' deve ser implementado pelas subclasses.")

    def _format_result(self, is_valid: bool, dado_original: Any, dado_normalizado: Any, mensagem: str, # dado_original e dado_normalizado agora são Any
                       details: Dict[str, Any], business_rule_applied: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata o dicionário de resultado padrão para todas as validações.
        Args:
            is_valid (bool): Indica se a validação foi bem-sucedida.
            dado_original (Any): O dado original que foi submetido para validação.
            dado_normalizado (Any): O dado após a normalização, se aplicável (pode ser string ou dicionário).
            mensagem (str): Uma mensagem descritiva do resultado da validação.
            details (Dict[str, Any]): Um dicionário com detalhes adicionais da validação.
            business_rule_applied (Dict[str, Any]): Detalhes da regra de negócio aplicada.
        Returns:
            Dict[str, Any]: O dicionário de resultado formatado.
        """
        return {
            "is_valid": is_valid,
            "dado_original": dado_original, # Manteve o dado_original
            "dado_normalizado": dado_normalizado,
            "mensagem": mensagem,
            "origem_validacao": self.origin_name,
            "details": details,
            "business_rule_applied": business_rule_applied
        }

