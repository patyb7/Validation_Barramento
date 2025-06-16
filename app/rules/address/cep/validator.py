# app/rules/cep/validator.py

import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Códigos de Validação específicos para CEP
VAL_CEP001 = "VAL_CEP001" # CEP Válido
VAL_CEP002 = "VAL_CEP002" # CEP Inválido (formato/comprimento)
VAL_CEP003 = "VAL_CEP003" # Input vazio ou tipo errado
VAL_CEP004 = "VAL_CEP004" # CEP com dígitos sequenciais ou repetidos

class CEPValidator:
    """
    Validador específico para códigos de Endereçamento Postal (CEP) no Brasil.
    Implementa validação básica de formato e de padrões comuns de invalidez.
    """

    def __init__(self):
        logger.info("CEPValidator inicializado.")

    def validate(self, cep_number: str) -> Dict[str, Any]:
        """
        Valida um número de CEP brasileiro.
        
        Args:
            cep_number (str): O número de CEP a ser validado.

        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação, incluindo
                            is_valid, message, cleaned_data, source, validation_code e details.
        """
        original_cep = cep_number
        cleaned_cep = self._clean_cep(cep_number)
        
        is_valid = False
        message = "CEP inválido."
        details = {}
        source = "cep_validator"
        validation_code = VAL_CEP002 # Código padrão para inválido na validação pura

        if not original_cep or not isinstance(original_cep, str):
            message = "CEP deve ser uma string não vazia."
            details["reason"] = "empty_or_wrong_type"
            validation_code = VAL_CEP003
            return {
                "is_valid": False,
                "message": message,
                "cleaned_data": cleaned_cep,
                "source": source,
                "validation_code": validation_code,
                "details": details
            }

        # O CEP brasileiro tem 8 dígitos
        if len(cleaned_cep) == 8 and cleaned_cep.isdigit():
            # Regra de validação: não pode ser números sequenciais ou repetidos (ex: 11111111, 12345678)
            if self._is_sequential_or_repeated(cleaned_cep):
                is_valid = False
                message = "CEP inválido: sequencial ou com dígitos repetidos."
                details["format_valid"] = False
                details["reason"] = "sequential_or_repeated_digits"
                validation_code = VAL_CEP004
            else:
                is_valid = True
                message = "CEP válido."
                details["format_valid"] = True
                validation_code = VAL_CEP001 # Código para válido
                # Adicionar lógica para consulta a API externa de CEP, se necessário
                # Ex: via_cep_data = self._consult_via_cep(cleaned_cep)
                # details["via_cep_data"] = via_cep_data
        else:
            details["format_valid"] = False
            details["reason"] = "CEP deve conter 8 dígitos numéricos."
            validation_code = VAL_CEP002 # Reafirma código para inválido

        logger.info(f"Validação de CEP: '{original_cep}' -> Limpo: '{cleaned_cep}', Válido: {is_valid}, Mensagem: {message}, Código Validação: {validation_code}")

        return {
            "is_valid": is_valid,
            "message": message,
            "cleaned_data": cleaned_cep,
            "source": source,
            "validation_code": validation_code,
            "details": details
        }

    def _clean_cep(self, cep: str) -> str:
        """
        Remove caracteres não numéricos do CEP.
        """
        return re.sub(r'\D', '', cep) # Remove tudo que não for dígito

    def _is_sequential_or_repeated(self, s: str) -> bool:
        """
        Verifica se uma string de dígitos é sequencial (ex: 12345678)
        ou repetida (ex: 11111111).
        """
        if len(s) < 2:
            return False

        # Verifica repetidos (ex: 11111111)
        if s.count(s[0]) == len(s):
            return True

        # Verifica sequenciais (ex: 12345678 ou 87654321)
        is_increasing_sequential = all(int(s[i]) == int(s[i-1]) + 1 for i in range(1, len(s)))
        is_decreasing_sequential = all(int(s[i]) == int(s[i-1]) - 1 for i in range(1, len(s)))

        return is_increasing_sequential or is_decreasing_sequential