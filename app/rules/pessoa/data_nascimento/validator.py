# app/rules/data_nascimento/validator.py

import re
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional
from app.rules.base import BaseValidator

logger = logging.getLogger(__name__)

# Os códigos de regra foram movidos para dentro da classe DataNascimentoValidator
# class DataNascimentoRuleCodes:
#    RN_DN001 = "RN_DN001"  # Data de Nascimento válida e consistente
#    RN_DN002 = "RN_DN002"  # Formato de data de nascimento inválido (ex: DD/MM/AAAA)
#    RN_DN003 = "RN_DN003"  # Data de nascimento futura (ainda não ocorreu)
#    RN_DN004 = "RN_DN004"  # Idade inconsistente (ex: idade fornecida não corresponde à data) - SIMULADO/OPCIONAL
#    RN_DN005 = "RN_DN005"  # Idade menor que o permitido (ex: menor de 18)
#    RN_DN006 = "RN_DN006"  # Input vazio ou tipo inválido (não string, ou string vazia)

class DataNascimentoValidator(BaseValidator):
    """
    Validador para datas de nascimento.
    Verifica o formato (DD/MM/AAAA) e se a data não está no futuro.
    Pode ser estendido para verificar idade mínima/máxima.
    """
    # Códigos de Regra específicos para validação de Data de Nascimento
    RN_DN001 = "RN_DN001"  # Data de Nascimento válida e consistente
    RN_DN002 = "RN_DN002"  # Formato de data de nascimento inválido (ex: DD/MM/AAAA)
    RN_DN003 = "RN_DN003"  # Data de nascimento futura (ainda não ocorreu)
    RN_DN004 = "RN_DN004"  # Idade inconsistente (ex: idade fornecida não corresponde à data) - SIMULADO/OPCIONAL
    RN_DN005 = "RN_DN005"  # Idade menor que o permitido (ex: menor de 18)
    RN_DN006 = "RN_DN006"  # Input vazio ou tipo inválido (não string, ou string vazia)


    def __init__(self, expected_format: str = "%d/%m/%Y", min_age: int = 0):
        super().__init__(origin_name="data_nascimento_validator")
        self.expected_format = expected_format
        self.min_age = min_age
        logger.info(f"DataNascimentoValidator inicializado com formato esperado: {self.expected_format}.")

    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Valida uma data de nascimento.

        Args:
            data (Any): A data de nascimento a ser validada. Esperado string.
            **kwargs: Parâmetros adicionais (compatibilidade com BaseValidator).

        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação padronizado.
        """
        data_nasc_str = data
        logger.info(f"Iniciando validação de data de nascimento: {data_nasc_str}...")

        # 1. Verificação de Input Vazio ou Inválido
        if not isinstance(data_nasc_str, str) or not data_nasc_str.strip():
            return self._format_result(
                is_valid=False,
                dado_original=data_nasc_str,
                dado_normalizado=None,
                mensagem="Data de nascimento vazia ou tipo inválido.",
                details={"input_original": data_nasc_str},
                business_rule_applied={"code": self.RN_DN006, "type": "Data de Nascimento - Validação Primária", "name": "Input Vazio ou Inválido"}
            )
        
        normalized_data_nasc = data_nasc_str.strip()
        is_valid = False
        message = "Data de nascimento inválida."
        business_rule_code = self.RN_DN002 # Default para formato inválido
        
        details = {
            "input_original": data_nasc_str,
            "normalized_data": normalized_data_nasc,
            "parsed_date": None,
            "is_future_date": False,
            "age": None,
            "is_under_min_age": False,
            "reason": []
        }

        parsed_date: Optional[date] = None
        try:
            parsed_date = datetime.strptime(normalized_data_nasc, self.expected_format).date()
            details["parsed_date"] = parsed_date.isoformat() # Armazenar em formato ISO para consistência
            
            # Verificar se a data está no futuro
            today = date.today()
            if parsed_date > today:
                message = "Data de nascimento no futuro."
                business_rule_code = self.RN_DN003
                details["is_future_date"] = True
                details["reason"].append("future_date")
                is_valid = False
            else:
                is_valid = True
                message = "Data de nascimento válida."
                business_rule_code = self.RN_DN001
                
                # Calcular idade e verificar idade mínima
                age = today.year - parsed_date.year - ((today.month, today.day) < (parsed_date.month, parsed_date.day))
                details["age"] = age
                if self.min_age > 0 and age < self.min_age:
                    message = f"Data de nascimento válida, mas a idade ({age} anos) é menor que a idade mínima permitida ({self.min_age} anos)."
                    business_rule_code = self.RN_DN005
                    details["is_under_min_age"] = True
                    details["reason"].append("under_min_age")
                    is_valid = False # Considerar inválido se menor que a idade mínima

        except ValueError:
            message = f"Formato de data de nascimento inválido. Esperado '{self.expected_format}'."
            business_rule_code = self.RN_DN002
            details["reason"].append("invalid_format_parsing")
            is_valid = False
        except Exception as e:
            logger.error(f"Erro inesperado na validação de data de nascimento para '{data_nasc_str}': {e}", exc_info=True)
            message = f"Erro inesperado durante a validação da data de nascimento: {e}."
            business_rule_code = self.VAL_GENERIC_INVALID # Usar código genérico de inválido
            details["reason"].append("unexpected_error")
            is_valid = False

        # Se for inválido por formato, data futura ou idade mínima, retorna imediatamente
        if not is_valid:
            return self._format_result(
                is_valid=False,
                dado_original=data_nasc_str,
                dado_normalizado=normalized_data_nasc,
                mensagem=message,
                details=details,
                business_rule_applied={"code": business_rule_code, "type": "Data de Nascimento - Validação Primária", "name": message}
            )

        # Se passou em todas as validações, retorna válido
        return self._format_result(
            is_valid=True,
            dado_original=data_nasc_str,
            dado_normalizado=normalized_data_nasc,
            mensagem=message,
            details=details,
            business_rule_applied={"code": business_rule_code, "type": "Data de Nascimento - Validação Final", "name": message}
        )
