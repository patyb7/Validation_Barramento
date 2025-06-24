# app/rules/phone/validator.py

import re
import logging
import phonenumbers # Importar a biblioteca phonenumbers
from phonenumbers import PhoneNumberType, NumberParseException # Importar PhoneNumberType e NumberParseException
from typing import Optional, Dict, Any
from app.rules.base import BaseValidator

# Configuração de logging
logger = logging.getLogger(__name__)

## Configuração do "Database" Interno (regras em memória)
# Conjunto de DDDs Válidos para buscas eficientes (O(1)) no Brasil
DDD_VALIDOS_BR = {
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "21", "22", "24",
    "27", "28", "31", "32", "33", "34", "35", "37", "38", "41", "42", "43",
    "44", "45", "46", "47", "48", "49", "51", "53", "54", "55", "61", "62",
    "63", "64", "65", "66", "67", "68", "69", "71", "73", "74", "75", "77",
    "79", "81", "82", "83", "84", "85", "86", "87", "88", "89", "91", "92",
    "93", "94", "95", "96", "97", "98", "99"
}
# Códigos de serviço/emergência válidos para o Brasil (se `phonenumbers` não for usado)
SERVICE_EMERGENCY_NUMBERS_BR = {
    "190", # Polícia
    "192", # SAMU
    "193", # Bombeiros
    "100", # Direitos Humanos
    "180", # Central de Atendimento à Mulher
    "181", # Disque Denúncia
}
# Mapeamento de tipos de telefone do phonenumbers para nomes amigáveis em português
PHONE_TYPE_MAP = {
    None: "Desconhecido", 
}
# Mapeamento de country_code_hint (ISO 3166-1 alpha-2) para country_code_number (ITU E.164)
COUNTRY_CODE_HINT_TO_NUMBER = {
    "BR": 55,
    "US": 1,
    "CA": 1,
    "GB": 44, # UK
    "DE": 49, # Germany
    "FR": 33, # France
    "ES": 34, # Spain
    "PT": 351, # Portugal
    "AR": 54, # Argentina
    "MX": 52, # Mexico
}
# Códigos de Validação específicos para telefone (prefixo RNT_PHN - Regra de Negócio de Telefone)
RNT_PHN001 = "RNT_PHN001"     # Válido e possível via phonenumbers
RNT_PHN002 = "RNT_PHN002"     # Inválido via phonenumbers
RNT_PHN003 = "RNT_PHN003"     # Input vazio ou tipo errado
RNT_PHN004 = "RNT_PHN004"     # Possível mas não válido via phonenumbers
RNT_PHN005 = "RNT_PHN005"     # Erro de parsing do phonenumbers
RNT_PHN006 = "RNT_PHN006"     # Erro inesperado do phonenumbers
RNT_PHN010 = "RNT_PHN010"     # Validação BR via fallback: Celular/Fixo válido
RNT_PHN011 = "RNT_PHN011"     # Validação BR via fallback: DDD inválido
RNT_PHN012 = "RNT_PHN012"     # Validação BR via fallback: Comprimento/formato inválido para BR
RNT_PHN013 = "RNT_PHN013"     # Validação: Número sequencial/repetido
RNT_PHN014 = "RNT_PHN014"     # Validação internacional via fallback: Válido (E.164 básico)
RNT_PHN015 = "RNT_PHN015"     # Validação internacional via fallback: Comprimento inválido
RNT_PHN016 = "RNT_PHN016"     # Validação de serviço/emergência (ex: 190, 192)
RNT_PHN020 = "RNT_PHN020"     # Formato geral não reconhecido (fallback)

## Configuração e carregamento da biblioteca phonenumbers

PHONENUMBERS_AVAILABLE = True
try:
    import phonenumbers
    from phonenumbers import PhoneNumberType, NumberParseException # Garantir importação de PhoneNumberType e NumberParseException

    # Atualiza PHONE_TYPE_MAP com os enums reais de PhoneNumberType se phonenumbers está disponível
    PHONE_TYPE_MAP.update({
        phonenumbers.PhoneNumberType.UNKNOWN: "Desconhecido",
        phonenumbers.PhoneNumberType.FIXED_LINE: "Fixo",
        phonenumbers.PhoneNumberType.MOBILE: "Celular",
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixo ou Celular",
        phonenumbers.PhoneNumberType.TOLL_FREE: "Ligação Gratuita",
        phonenumbers.PhoneNumberType.PREMIUM_RATE: "Tarifa Premium",
        phonenumbers.PhoneNumberType.SHARED_COST: "Custo Compartilhado",
        phonenumbers.PhoneNumberType.VOIP: "VoIP",
        phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Número Pessoal",
        phonenumbers.PhoneNumberType.PAGER: "Pager",
        phonenumbers.PhoneNumberType.UAN: "UAN (Universal Access Number)",
        phonenumbers.PhoneNumberType.VOICEMAIL: "Correio de Voz",
    })

except ImportError:
    PHONENUMBERS_AVAILABLE = False
    logger.warning("A biblioteca 'phonenumbers' não está instalada. A validação de telefone será menos precisa e dependerá de regras de fallback.")
except Exception as e:
    PHONENUMBERS_AVAILABLE = False
    logger.error(f"Erro inesperado ao carregar ou configurar phonenumbers: {e}. Desativando phonenumbers.")


class PhoneValidator(BaseValidator): 
    """
    Validador de números de telefone que utiliza a biblioteca phonenumbers
    para validação robusta e inclui regras de fallback (em memória) para
    casos onde phonenumbers não é aplicável ou não está disponível.

    O método `validate` retorna um dicionário padronizado com as chaves:
    - is_valid (bool): Se o dado é válido.
    - dado_normalizado (str): O dado normalizado (ex: E.164).
    - mensagem (str): Mensagem explicativa do resultado.
    - origem_validacao (str): A fonte da validação (e.g., "phonenumbers", "fallback_br").
    - details (dict): Detalhes específicos da validação.
    - business_rule_applied (dict): Detalhes da regra de negócio aplicada.
    """

    def __init__(self):
        super().__init__(origin_name="phone_validator")
        logger.info("PhoneValidator inicializado.")

    @staticmethod
    def _get_phone_type_name_safe(parsed_number_obj: phonenumbers.PhoneNumber) -> str:
        """
        Função auxiliar estática para obter o nome amigável do tipo de telefone.
        Corrige o erro 'module 'phonenumbers' has no attribute 'get_number_type''.
        """
        if PHONENUMBERS_AVAILABLE and parsed_number_obj:
            # CORREÇÃO: Usar o atributo 'number_type' do objeto PhoneNumber
            num_type = parsed_number_obj.number_type 
            return PHONE_TYPE_MAP.get(num_type, f"Tipo Desconhecido ({num_type})") 
        return PHONE_TYPE_MAP.get(None)

    def _clean_number(self, phone_number: str) -> str:
        """Remove caracteres não-dígitos do número."""
        return re.sub(r'\D', '', phone_number)

    def _is_sequential_or_repeated(self, cleaned_number: str) -> bool:
        """Verifica se o número tem 4 ou mais dígitos sequenciais ou repetidos."""
        if len(cleaned_number) < 7: 
            return False

        for i in range(len(cleaned_number) - 3):
            subset = cleaned_number[i:i+4]
            if all(d.isdigit() for d in subset): 
                s0, s1, s2, s3 = int(subset[0]), int(subset[1]), int(subset[2]), int(subset[3])
                if (s0 + 1 == s1 and s1 + 1 == s2 and s2 + 1 == s3): 
                    return True
                if (s0 - 1 == s1 and s1 - 1 == s2 and s2 - 1 == s3): 
                    return True

        for i in range(len(cleaned_number) - 3):
            subset = cleaned_number[i:i+4]
            if subset[0] == subset[1] == subset[2] == subset[3]:
                return True
        return False

    def _is_brazilian_ddd_valid(self, ddd: str) -> bool:
        """Verifica se o DDD é um DDD brasileiro válido."""
        return ddd in DDD_VALIDOS_BR

    def _normalize_phone_number(self, phone_number: str, country_code_hint: Optional[str]) -> str:
        """
        Normaliza o número de telefone. Tenta usar phonenumbers se disponível.
        Retorna o número limpo mesmo se a normalização E.164 falhar.
        Prioriza o formato E.164.
        """
        cleaned_number = self._clean_number(phone_number)

        if not cleaned_number:
            return ""

        if PHONENUMBERS_AVAILABLE:
            try:
                parsed_number = phonenumbers.parse(cleaned_number, country_code_hint.upper() if country_code_hint else None)

                if phonenumbers.is_possible_number(parsed_number):
                    return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
                else:
                    return cleaned_number 
            except NumberParseException as e:
                logger.debug(f"Parsing error in phonenumbers for '{phone_number}': {e}")
                return cleaned_number
            except Exception as e:
                logger.error(f"Unexpected error in phonenumbers.parse for '{phone_number}': {e}", exc_info=True)
                return cleaned_number
        else:
            if cleaned_number.startswith("+"):
                return cleaned_number

            if country_code_hint and country_code_hint.upper() in COUNTRY_CODE_HINT_TO_NUMBER:
                country_num_code = COUNTRY_CODE_HINT_TO_NUMBER[country_code_hint.upper()]

                if country_code_hint.upper() == "BR" and (len(cleaned_number) == 10 or len(cleaned_number) == 11):
                    if cleaned_number.startswith("0") and len(cleaned_number) > 2:
                        cleaned_number = cleaned_number[1:]

                    if not cleaned_number.startswith(str(country_num_code)):
                        return f"+{country_num_code}{cleaned_number}"
                    return cleaned_number 
                elif not cleaned_number.startswith(str(country_num_code)):
                    return f"+{country_num_code}{cleaned_number}"

            return cleaned_number 

    async def validate(self, data: Any, country_hint: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Valida um número de telefone aplicando uma sequência de regras:
        1. Normalização do número.
        2. Validação com phonenumbers (se disponível e aplicável).
        3. Validação de fallback usando regras em memória (DDDs, padrões básicos, sequenciais/repetidos).
        """
        phone_number = data

        details = {
            "input_original": phone_number,
            "country_hint_used": country_hint.upper() if country_hint else None,
            "type_detected": None,
            "phonenumbers_possible": False,
            "phonenumbers_valid": False,
            "international_format_generated": False,
            "country_code_detected": None,
            "national_number": None,
        }

        if not phone_number or not isinstance(phone_number, str):
            return self._format_result(
                is_valid=False,
                dado_normalizado=None,
                mensagem="Número de telefone deve ser uma string não vazia.",
                details=details,
                business_rule_applied={"code": RNT_PHN003, "type": "phone"}
            )

        normalized_number = self._normalize_phone_number(phone_number, country_hint)

        if not normalized_number:
            return self._format_result(
                is_valid=False,
                dado_normalizado=None,
                mensagem="Número de telefone vazio após limpeza ou não contém dígitos válidos.",
                details=details,
                business_rule_applied={"code": RNT_PHN003, "type": "phone"}
            )

        digits_only = self._clean_number(phone_number)

        if PHONENUMBERS_AVAILABLE:
            try:
                parsed_number = phonenumbers.parse(normalized_number, country_hint.upper() if country_hint else None)
                details["phonenumbers_possible"] = phonenumbers.is_possible_number(parsed_number)
                details["phonenumbers_valid"] = phonenumbers.is_valid_number(parsed_number)
                details["country_code_detected"] = parsed_number.country_code
                details["national_number"] = parsed_number.national_number

                if details["phonenumbers_valid"]:
                    details["type_detected"] = self._get_phone_type_name_safe(parsed_number)
                    if self._is_sequential_or_repeated(self._clean_number(phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164))):
                        return self._format_result(
                            is_valid=False,
                            dado_normalizado=phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164),
                            mensagem="Número de telefone inválido: sequencial ou com dígitos repetidos (mesmo válido pelo phonenumbers).",
                            details=details,
                            business_rule_applied={"code": RNT_PHN013, "type": "phone"}
                        )
                    return self._format_result(
                        is_valid=True,
                        dado_normalizado=phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164),
                        mensagem="Número de telefone válido (via phonenumbers).",
                        details=details,
                        business_rule_applied={"code": RNT_PHN001, "type": "phone"}
                    )

                elif details["phonenumbers_possible"]:
                    pass # Continue para as regras de fallback.
                else:
                    pass # Continue para as regras de fallback.

            except NumberParseException as e:
                logger.debug(f"NumberParseException for '{normalized_number}': {e}. Trying fallback.")
            except Exception as e:
                logger.error(f"Unexpected error in phonenumbers for '{normalized_number}': {e}", exc_info=True)
        else:
            logger.info("Biblioteca 'phonenumbers' não disponível. Usando validação de fallback.")

        # Lógica de Fallback:
        if len(digits_only) == 3 and digits_only.isdigit():
            if digits_only in SERVICE_EMERGENCY_NUMBERS_BR:
                details["type_detected"] = "Emergência/Serviço BR"
                details["country_code_detected"] = 55 
                try:
                    details["national_number"] = int(digits_only)
                except ValueError:
                    details["national_number"] = None
                return self._format_result(
                    is_valid=True,
                    dado_normalizado=digits_only,
                    mensagem=f"Número de serviço/emergência válido ({digits_only} via fallback).",
                    details=details,
                    business_rule_applied={"code": RNT_PHN016, "type": "phone"}
                )
            else:
                return self._format_result(
                    is_valid=False,
                    dado_normalizado=normalized_number,
                    mensagem="Número de 3 dígitos não reconhecido como serviço/emergência (via fallback).",
                    details=details,
                    business_rule_applied={"code": RNT_PHN020, "type": "phone"}
                )

        if self._is_sequential_or_repeated(digits_only):
            return self._format_result(
                is_valid=False,
                dado_normalizado=normalized_number,
                mensagem="Número de telefone inválido: sequencial ou com dígitos repetidos.",
                details=details,
                business_rule_applied={"code": RNT_PHN013, "type": "phone"}
            )

        if normalized_number.startswith('+'):
            temp_number_without_plus = normalized_number[1:]

            match = re.match(r'^(\d{1,4})(\d+)$', temp_number_without_plus)
            if match:
                country_code_str = match.group(1)
                national_number_part = match.group(2)

                if 7 <= len(national_number_part) <= 15: 
                    details["type_detected"] = "Internacional Básico"
                    try:
                        details["country_code_detected"] = int(country_code_str)
                    except ValueError:
                        details["country_code_detected"] = None
                    try:
                        details["national_number"] = int(national_number_part)
                    except ValueError:
                        details["national_number"] = None
                    return self._format_result(
                        is_valid=True,
                        dado_normalizado=normalized_number,
                        mensagem="Número internacional válido (formato E.164 básico via fallback).",
                        details=details,
                        business_rule_applied={"code": RNT_PHN014, "type": "phone"}
                    )
                else:
                    return self._format_result(
                        is_valid=False,
                        dado_normalizado=normalized_number,
                        mensagem="Número internacional com comprimento de dígitos inválido (via fallback).",
                        details=details,
                        business_rule_applied={"code": RNT_PHN015, "type": "phone"}
                    )
            else:
                return self._format_result(
                    is_valid=False,
                    dado_normalizado=normalized_number,
                    mensagem="Número internacional com formato básico não reconhecido (via fallback).",
                    details=details,
                    business_rule_applied={"code": RNT_PHN020, "type": "phone"}
                )

        is_br_hint = country_hint and country_hint.upper() == "BR"
        looks_like_br = (len(digits_only) >= 10 and digits_only.isdigit() and digits_only[:2] in DDD_VALIDOS_BR)

        if is_br_hint or looks_like_br:
            if 10 <= len(digits_only) <= 11:
                ddd = digits_only[:2]
                numero_principal = digits_only[2:]

                if not self._is_brazilian_ddd_valid(ddd):
                    details["country_code_detected"] = 55
                    try:
                        details["national_number"] = int(digits_only)
                    except ValueError:
                        details["national_number"] = None
                    return self._format_result(
                        is_valid=False,
                        dado_normalizado=normalized_number,
                        mensagem=f"DDD '{ddd}' inválido para o Brasil (via fallback).",
                        details=details,
                        business_rule_applied={"code": RNT_PHN011, "type": "phone"}
                    )
                else:
                    if len(digits_only) == 11 and numero_principal.startswith('9'):
                        details["type_detected"] = "Celular BR"
                        details["country_code_detected"] = 55
                        try:
                            details["national_number"] = int(digits_only)
                        except ValueError:
                            details["national_number"] = None
                        return self._format_result(
                            is_valid=True,
                            dado_normalizado=f"+55{digits_only}", 
                            mensagem="Número de telefone celular brasileiro válido (via fallback).",
                            details=details,
                            business_rule_applied={"code": RNT_PHN010, "type": "phone"}
                        )
                    elif len(digits_only) == 10 and numero_principal[0] in ('2', '3', '4', '5'): 
                        details["type_detected"] = "Fixo BR"
                        details["country_code_detected"] = 55
                        try:
                            details["national_number"] = int(digits_only)
                        except ValueError:
                            details["national_number"] = None
                        return self._format_result(
                            is_valid=True,
                            dado_normalizado=f"+55{digits_only}", 
                            mensagem="Número de telefone fixo brasileiro válido (via fallback).",
                            details=details,
                            business_rule_applied={"code": RNT_PHN010, "type": "phone"}
                        )
                    else:
                        details["country_code_detected"] = 55
                        try:
                            details["national_number"] = int(digits_only)
                        except ValueError:
                            details["national_number"] = None
                        return self._format_result(
                            is_valid=False,
                            dado_normalizado=normalized_number,
                            mensagem="Número de telefone brasileiro com estrutura inválida (DDD + número).",
                            details=details,
                            business_rule_applied={"code": RNT_PHN012, "type": "phone"}
                        )
            else: 
                details["country_code_detected"] = 55
                try:
                    details["national_number"] = int(digits_only)
                except ValueError:
                    details["national_number"] = None
                return self._format_result(
                    is_valid=False,
                    dado_normalizado=normalized_number,
                    mensagem="Número de telefone brasileiro com comprimento inválido (10 ou 11 dígitos esperados).",
                    details=details,
                    business_rule_applied={"code": RNT_PHN012, "type": "phone"}
                )
        return self._format_result(
            is_valid=False,
            dado_normalizado=normalized_number,
            mensagem="Número de telefone com formato ou comprimento não reconhecido (via fallback).",
            details=details,
            business_rule_applied={"code": RNT_PHN020, "type": "phone"}
        )
    def _format_result(self, is_valid: bool, dado_normalizado: Optional[str], mensagem: str, details: Dict[str, Any], business_rule_applied: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata o resultado da validação em um dicionário padronizado.
        """
        return {
            "is_valid": is_valid,
            "dado_normalizado": dado_normalizado,
            "mensagem": mensagem,
            "origem_validacao": self.origin_name,
            "details": details,
            "business_rule_applied": business_rule_applied
        }
# Exemplo de uso:
# if __name__ == "__main__":
#     validator = PhoneValidator()
#     result = validator.validate("+5511987654321", country_hint="BR")
#     print(result)
#     # Saída esperada: {'is_valid': True, 'dado_normalizado': '+5511987654321', ...}
#     # Se o número for inválido, a mensagem explicará o porquê.
#     result = validator.validate("1234567890", country_hint="BR")
#     print(result)
#     # Saída esperada: {'is_valid': False, 'dado_normalizado': None, 'mensagem': 'Número de telefone brasileiro com comprimento inválido (10 ou 11 dígitos esperados).', ...}
#     # Se o número for inválido, a mensagem explicará o porquê.
#     result = validator.validate("190", country_hint="BR")
#     print(result)
#     # Saída esperada: {'is_valid': True, 'dado_normalizado': '190', 'mensagem': 'Número de serviço/emergência válido (190 via fallback).', ...}
#     # Se o número for um serviço de emergência, a mensagem explicará o porquê.
#     result = validator.validate("1234", country_hint="BR")
#     print(result)
#     # Saída esperada: {'is_valid': False, 'dado_normalizado': None, 'mensagem': 'Número de telefone com formato ou comprimento não reconhecido (via fallback).', ...}
#     # Se o número for inválido, a mensagem explicará o porquê.
#     result = validator.validate("9999999999", country_hint="BR")
#     print(result)
#     # Saída esperada: {'is_valid': False, 'dado_normalizado': None, 'mensagem': 'Número de telefone inválido: sequencial ou com dígitos repetidos.', ...}
#     # Se o número for inválido, a mensagem explicará o porquê.
#     result = validator.validate("12345678901234567890", country_hint="BR")
#     print(result)
#     # Saída esperada: {'is_valid': False, 'dado_normalizado': None, 'mensagem': 'Número de telefone com formato ou comprimento não reconhecido (via fallback).', ...}
#     # Se o número for inválido, a mensagem explicará o porquê.
#     result = validator.validate("1234567890", country_hint="US")
#     print(result)
#     # Saída esperada: {'is_valid': False, 'dado_normalizado': None, 'mensagem': 'Número de telefone com formato ou comprimento não reconhecido (via fallback).', ...}
#     # Se o número for inválido, a mensagem explicará o porquê.
#     result = validator.validate("+1234567890", country_hint="US")
#     print(result)
#     # Saída esperada: {'is_valid': True, 'dado_normalizado': '+1234567890', 'mensagem': 'Número internacional válido (formato E.164 básico via fallback).', ...}
#     # Se o número for válido, a mensagem explicará o porquê.
#     result = validator.validate("1234567890", country_hint="US")
#     print(result)
#     # Saída esperada: {'is_valid': False, 'dado_normalizado': None, 'mensagem': 'Número de telefone com formato ou comprimento não reconhecido (via fallback).', ...}
#     # Se o número for inválido, a mensagem explicará o porquê.
#     result = validator.validate("12345678901234567890", country_hint="US")
#     print(result)
#     # Saída esperada: {'is_valid': False, 'dado_normalizado': None, 'mensagem': 'Número de telefone com formato ou comprimento não reconhecido (via fallback).', ...}
#     # Se o número for inválido, a mensagem explicará o porquê.
#     result = validator.validate("1234567890", country_hint="BR")
#     print(result)
#     # Saída esperada: {'is_valid': False, 'dado_normalizado': None, 'mensagem': 'Número de telefone com formato ou comprimento não reconhecido (via fallback).', ...}
#     # Se o número for inválido, a mensagem explicará o porquê.
#     result = validator.validate("12345678901234567890", country_hint="BR")
#     print(result)