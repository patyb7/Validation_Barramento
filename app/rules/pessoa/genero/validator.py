# app/rules/pessoa/genero/validator.py
import logging
from typing import Dict, Any, List, Optional
from app.rules.base import BaseValidator

logger = logging.getLogger(__name__)

class SexoValidator(BaseValidator):
    """
    Validador para o campo 'sexo' (gênero) de uma pessoa.
    Garante que o valor fornecido esteja dentro de uma lista de opções permitidas.
    """
    # Códigos de Regra específicos para validação de Sexo/Gênero
    RN_SEXO001 = "RN_SEXO001"  # Gênero válido
    RN_SEXO002 = "RN_SEXO002"  # Gênero inválido (não está nas opções permitidas)
    RN_SEXO003 = "RN_SEXO003"  # Input vazio ou tipo inválido (não string, ou string vazia)

    def __init__(self, allowed_genders: Optional[List[str]] = None):
        super().__init__(origin_name="sexo_validator")
        self.allowed_genders = [g.upper() for g in allowed_genders] if allowed_genders else ["MASCULINO", "FEMININO", "OUTRO", "NAO INFORMADO"]
        logger.info(f"SexoValidator inicializado com gêneros permitidos: {self.allowed_genders}.")

    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Valida o campo de gênero.

        Args:
            data (Any): O valor do gênero a ser validado. Esperado uma string.
            **kwargs: Parâmetros adicionais (compatibilidade com BaseValidator).

        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação padronizado.
        """
        gender_input = data
        logger.info(f"Iniciando validação de gênero: {gender_input}...")

        # 1. Verificação de Input Vazio ou Inválido
        if not isinstance(gender_input, str) or not gender_input.strip():
            return self._format_result(
                is_valid=False,
                dado_original=gender_input, # Adicionado dado_original
                dado_normalizado=None,
                mensagem="Gênero vazio ou tipo inválido.",
                details={"input_original": gender_input},
                business_rule_applied={"code": self.RN_SEXO003, "type": "Gênero - Validação Primária", "name": "Input de Gênero Vazio ou Inválido"}
            )
        
        normalized_gender = gender_input.strip().upper()
        is_valid = False
        message = "Gênero inválido."
        business_rule_code = self.RN_SEXO002 # Default para inválido
        
        details = {
            "input_original": gender_input,
            "normalized_gender": normalized_gender,
            "allowed_genders": self.allowed_genders,
            "reason": []
        }

        if normalized_gender in self.allowed_genders:
            is_valid = True
            message = "Gênero válido."
            business_rule_code = self.RN_SEXO001
        else:
            details["reason"].append("not_in_allowed_list")
            message = f"Gênero '{gender_input}' não está nas opções permitidas: {', '.join(self.allowed_genders)}."
            business_rule_code = self.RN_SEXO002

        return self._format_result(
            is_valid=is_valid,
            dado_original=gender_input, # Adicionado dado_original
            dado_normalizado=normalized_gender,
            mensagem=message,
            details=details,
            business_rule_applied={"code": business_rule_code, "type": "Gênero - Validação Final", "name": message}
        )
