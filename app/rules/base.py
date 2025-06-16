# app/rules/base.py

from typing import Dict, Any

class BaseValidationRule:
    """
    Classe base abstrata para todas as regras de validação.
    Define uma interface comum para execução e metadados.
    """
    PREFIX = "GEN" # Prefixo genérico, deve ser sobrescrito pelas classes filhas (ex: RNT, RNC)

    def __init__(self, code: str, description: str):
        if not code.startswith(self.PREFIX):
            raise ValueError(f"Código da regra '{code}' deve começar com o prefixo '{self.PREFIX}'.")
        self.code = code
        self.description = description

    def apply(self, data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplica a regra de validação.
        Deve ser implementado pelas classes filhas.
        Retorna um dicionário com o resultado da validação (sucesso, mensagem, metadados).
        """
        raise NotImplementedError("O método 'apply' deve ser implementado pela classe filha.")

    def __str__(self):
        return f"{self.code}: {self.description}"