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
    # Códigos de Regra específicos para validação de Nome (Padronização RN_NOMExxx)
    RN_NOME001 = "RN_NOME001" # Nome válido e normalizado
    RN_NOME002 = "RN_NOME002" # Nome inválido: formato incorreto (ex: apenas um nome ou caracteres inválidos)
    RN_NOME003 = "RN_NOME003" # Nome inválido: vazio ou tipo incorreto
    RN_NOME004 = "RN_NOME004" # Nome inválido: comprimento insuficiente (ex: muito curto)

    def __init__(self):
        """
        Inicializa o NomeValidator.
        """
        super().__init__(origin_name="nome_validator")
        logger.info("NomeValidator inicializado.")
    
    async def validate(self, nome: Any, **kwargs) -> Dict[str, Any]: # Nome agora é Any para a primeira checagem
        """
        Valida o nome de uma pessoa.
        Args:
            nome (Any): O nome a ser validado. Esperado uma string.
            **kwargs: Parâmetros adicionais (compatibilidade com BaseValidator).
        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação.
        """
        logger.info(f"Iniciando validação de nome: {nome}")

        # 1. Verifica se o input é uma string e não está vazio após remover espaços em branco
        if not isinstance(nome, str) or not nome.strip():
            return self._format_result(
                is_valid=False,
                dado_original=nome, # Inclui o dado original
                dado_normalizado=None,
                mensagem="Nome vazio ou tipo inválido. O nome deve ser uma string não vazia.",
                details={"input_original": nome, "reason": ["empty_or_invalid_type"]},
                business_rule_applied={"code": self.RN_NOME003, "type": "Nome - Validação Primária", "name": "Input de Nome Inválido"}
            )
        
        # Normaliza o nome: remove múltiplos espaços, tira espaços extras e capitaliza cada palavra
        normalized_name = re.sub(r'\s+', ' ', nome).strip().title()

        # 2. Validação básica: verifica se o nome tem pelo menos duas partes (nome e sobrenome)
        # E se o comprimento total do nome normalizado é razoável (ex: > 2 caracteres para evitar "Eu" como válido)
        name_parts = normalized_name.split(' ')
        
        is_valid = True
        message = "Nome válido e normalizado."
        code = self.RN_NOME001
        details = {
            "input_original": nome,
            "normalized_attempt": normalized_name,
            "has_min_parts": False,
            "min_length_met": False,
            "reason": []
        }

        if len(name_parts) < 2:
            is_valid = False
            message = "Nome inválido: deve conter pelo menos um nome e um sobrenome."
            code = self.RN_NOME002
            details["reason"].append("missing_surname")
        else:
            details["has_min_parts"] = True

        if len(normalized_name) < 3: # Exemplo: "Eu" não seria um nome válido
            is_valid = False
            message = "Nome inválido: muito curto. O nome deve ter pelo menos 3 caracteres."
            code = self.RN_NOME004
            details["reason"].append("name_too_short")
        else:
            details["min_length_met"] = True

        # Se alguma das verificações de 'is_valid' resultou em False, ajusta a mensagem e o código
        if not is_valid:
            normalized_name_for_output = None # Se inválido, não retorna nome normalizado como "válido"
            # Prioriza a mensagem mais relevante se houver múltiplos motivos de falha
            if "missing_surname" in details["reason"] and "name_too_short" in details["reason"]:
                 message = "Nome inválido: muito curto e/ou faltando sobrenome."
                 code = self.RN_NOME002 # Pode ser RN_NOME002 se considerar formato, ou RN_NOME004 para comprimento
            elif "missing_surname" in details["reason"]:
                message = "Nome inválido: deve conter pelo menos um nome e um sobrenome."
                code = self.RN_NOME002
            elif "name_too_short" in details["reason"]:
                message = "Nome inválido: muito curto. O nome deve ter pelo menos 3 caracteres."
                code = self.RN_NOME004

            logger.debug(f"Validação de nome para '{nome}': {message}")

            return self._format_result(
                is_valid=is_valid,
                dado_original=nome,
                dado_normalizado=normalized_name_for_output, # Retorna None se inválido
                mensagem=message,
                details=details,
                business_rule_applied={"code": code, "type": "Nome - Validação", "name": "Validação de Nome Completo"}
            )
        
        # Se chegou aqui, o nome é válido
        logger.debug(f"Validação de nome para '{nome}': {message}")
        
        return self._format_result(
            is_valid=is_valid,
            dado_original=nome,
            dado_normalizado=normalized_name,
            mensagem=message,
            details=details,
            business_rule_applied={"code": code, "type": "Nome - Validação", "name": "Validação de Nome Completo"}
        )