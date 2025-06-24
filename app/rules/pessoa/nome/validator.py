# app/rules/pessoa/nome/validator.py
import logging
from typing import Dict, Any, Optional
import re

from app.rules.base import BaseValidator # Importa a classe BaseValidator

logger = logging.getLogger(__name__)

class NomeValidator(BaseValidator):
    """
    Validador de nomes de pessoas.
    Verifica se o nome é uma string não vazia e tenta padronizar a capitalização.
    Pode ser estendido para incluir validações mais complexas, como presença de sobrenome.
    """
    def __init__(self):
        """
        Inicializa o NomeValidator.
        """
        super().__init__(origin_name="nome_validator")
        logger.info("NomeValidator inicializado.")
    
    async def validate(self, nome: str, **kwargs) -> Dict[str, Any]:
        """
        Valida o nome de uma pessoa.
        Args:
            nome (str): O nome a ser validado.
            **kwargs: Parâmetros adicionais (compatibilidade com BaseValidator).
        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação.
        """
        # Verifica se o input é uma string e não está vazio após remover espaços em branco
        if not isinstance(nome, str) or not nome.strip():
            return self._format_result(
                is_valid=False,
                dado_normalizado=None,
                mensagem="Nome vazio ou tipo inválido. O nome deve ser uma string não vazia.",
                details={"input_original": nome},
                business_rule_applied={"code": self.VAL_GENERIC_EMPTY, "type": "Nome - Validação Primária", "name": "Nome Inválido"}
            )
        
        # Remove múltiplos espaços em branco e capitaliza cada palavra
        normalized_name = re.sub(r'\s+', ' ', nome).strip().title()
        
        # Validação básica: verifica se o nome tem pelo menos duas partes (nome e sobrenome)
        # Esta é uma regra comum, mas pode ser ajustada conforme a necessidade.
        is_valid = len(normalized_name.split(' ')) >= 2 and len(normalized_name) > 2
        
        if is_valid:
            message = "Nome válido e normalizado."
            code = self.VAL_GENERIC_VALID
        else:
            message = "Nome inválido. Deve conter nome e sobrenome e ser uma string válida."
            code = self.VAL_GENERIC_INVALID
            normalized_name = None # Não normaliza se o nome for considerado inválido

        logger.debug(f"Validação de nome para '{nome}': {message}")
        
        return self._format_result(
            is_valid=is_valid,
            dado_normalizado=normalized_name,
            mensagem=message,
            details={"input_original": nome, "normalized_attempt": normalized_name, "has_min_parts": (len(normalized_name.split(' ')) >= 2)},
            business_rule_applied={"code": code, "type": "Nome - Validação", "name": "Validação de Nome Completo"}
        )

    def _format_result(self, is_valid: bool, dado_normalizado: Optional[str], mensagem: str, details: Dict[str, Any], business_rule_applied: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata o resultado da validação.
        """
        return {
            "is_valid": is_valid,
            "dado_normalizado": dado_normalizado,
            "mensagem": mensagem,
            "details": details,
            "business_rule_applied": business_rule_applied
        }
# Fim do código
# Este validador pode ser usado em qualquer parte do sistema onde seja necessário validar nomes de pessoas.
# Ele pode ser facilmente integrado com outros validadores ou regras de negócio, mantendo a consistency e a extensibilidade do sistema.
# Além disso, o uso de logging permite rastrear facilmente o fluxo de validação e identificar problemas potenciais.
# A estrutura do código segue as melhores práticas de design, separando a lógica de validação em uma classe dedicada que herda de uma base de validadores.
# Isso facilita a manutenção e a adição de novas regras de validação no futuro.