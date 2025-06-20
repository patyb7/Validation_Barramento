# app/rules/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BaseValidator(ABC):
    """
    Classe base abstrata para todos os validadores da aplicação.
    Define uma interface comum para validação de dados e formatação de resultados.
    """
    def __init__(self, origin_name: str):
        self.origin_name = origin_name
        logger.debug(f"BaseValidator inicializado para origem: {self.origin_name}")

    @abstractmethod
    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Método abstrato para validação de dados.
        Deve ser implementado por todas as subclasses de validadores.

        Args:
            data (Any): Os dados a serem validados. Pode ser uma string, número, dicionário, etc.
            **kwargs: Parâmetros adicionais específicos do validador (ex: country_hint para telefone).

        Returns:
            Dict[str, Any]: Um dicionário padronizado com o resultado da validação, incluindo:
                            - "is_valid" (bool): Se o dado é considerado válido.
                            - "dado_normalizado" (Optional[str]): O dado após limpeza/normalização.
                            - "mensagem" (str): Mensagem explicativa do resultado.
                            - "origem_validacao" (str): A origem da validação (nome do validador).
                            - "details" (dict): Detalhes específicos da validação.
                            - "business_rule_applied" (dict): Detalhes da regra de negócio aplicada.
        """
        pass

    def _format_result(
        self,
        is_valid: bool,
        dado_normalizado: Optional[str],
        mensagem: str,
        details: Optional[Dict[str, Any]] = None,
        business_rule_applied: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Formata o resultado da validação de forma padronizada.
        """
        if details is None:
            details = {}
        if business_rule_applied is None:
            business_rule_applied = {}

        return {
            "is_valid": is_valid,
            "dado_normalizado": dado_normalizado,
            "mensagem": mensagem,
            "origem_validacao": self.origin_name,
            "details": details,
            "business_rule_applied": business_rule_applied
        }
