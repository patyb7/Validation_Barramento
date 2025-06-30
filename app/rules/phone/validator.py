import re
import logging
from typing import Optional, Dict, Any
from app.rules.base import BaseValidator
from abc import ABC, abstractmethod

# Configuração de logging
logger = logging.getLogger(__name__)

## Configuração do "Database" Interno (regras em memória).Conjunto de DDDs Válidos para buscas eficientes (O(1)) no Brasil
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
    None: "Desconhecido", # Para o caso de phonenumbers.get_number_type retornar None
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
# Códigos de Validação específicos para telefone (prefixo VAL_PHN)
VAL_PHN001 = "VAL_PHN001"     # Válido e possível via phonenumbers
VAL_PHN002 = "VAL_PHN002"     # Inválido via phonenumbers
VAL_PHN003 = "VAL_PHN003"     # Input vazio ou tipo errado
VAL_PHN004 = "VAL_PHN004"     # Possível mas não válido via phonenumbers
VAL_PHN005 = "VAL_PHN005"     # Erro de parsing do phonenumbers
VAL_PHN006 = "VAL_PHN006"     # Erro inesperado do phonenumbers
VAL_PHN010 = "VAL_PHN010"     # Validação BR via fallback: Celular/Fixo válido
VAL_PHN011 = "VAL_PHN011"     # Validação BR via fallback: DDD inválido
VAL_PHN012 = "VAL_PHN012"     # Validação BR via fallback: Comprimento/formato inválido para BR
VAL_PHN013 = "VAL_PHN013"     # Validação: Número sequencial/repetido
VAL_PHN014 = "VAL_PHN014"     # Validação internacional via fallback: Válido (E.164 básico)
VAL_PHN015 = "VAL_PHN015"     # Validação internacional via fallback: Comprimento inválido
VAL_PHN016 = "VAL_PHN016"     # Validação de serviço/emergência (ex: 190, 192)
VAL_PHN020 = "VAL_PHN020"     # Formato geral não reconhecido (fallback)

## Configuração e Carregamento da Biblioteca `phonenumbers`

PHONENUMBERS_AVAILABLE = True
try:
    import phonenumbers
    from phonenumbers import PhoneNumberType, NumberParseException

    # Atualiza PHONE_TYPE_MAP com os enums reais de PhoneNumberType se phonenumbers está disponível
    PHONE_TYPE_MAP.update({
        PhoneNumberType.UNKNOWN: "Desconhecido",
        PhoneNumberType.FIXED_LINE: "Fixo",
        PhoneNumberType.MOBILE: "Celular",
        PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixo ou Celular",
        PhoneNumberType.TOLL_FREE: "Ligação Gratuita",
        PhoneNumberType.PREMIUM_RATE: "Tarifa Premium",
        PhoneNumberType.SHARED_COST: "Custo Compartilhado",
        PhoneNumberType.VOIP: "VoIP",
        PhoneNumberType.PERSONAL_NUMBER: "Número Pessoal",
        PhoneNumberType.PAGER: "Pager",
        PhoneNumberType.UAN: "UAN (Universal Access Number)",
        PhoneNumberType.VOICEMAIL: "Correio de Voz",
        
    })

except ImportError:
    PHONENUMBERS_AVAILABLE = False
    logger.warning("A biblioteca 'phonenumbers' não está instalada. A validação de telefone será menos precisa e dependerá de regras de fallback.")
except Exception as e:
    PHONENUMBERS_AVAILABLE = False
    logger.error(f"Erro inesperado ao carregar ou configurar phonenumbers: {e}. Desativando phonenumbers.")


## Classe `PhoneValidator`

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
    def __init__(self, db_manager: Any): # Adicionei o tipo 'Any' para db_manager para flexibilidade
        super().__init__(origin_name="phone_validator", db_manager=db_manager)
        logger.info("PhoneValidator inicializado.")

    @staticmethod
    def _get_phone_type_name_safe(parsed_number_obj) -> str:
        """
        Função auxiliar estática para obter o nome amigável do tipo de telefone.
        Garante que mesmo que o type não esteja no mapeamento, retorne algo útil.
        """
        if PHONENUMBERS_AVAILABLE and parsed_number_obj:
            num_type = phonenumbers.get_number_type(parsed_number_obj)
            return PHONE_TYPE_MAP.get(num_type, f"Tipo Desconhecido ({num_type.name})")
        return PHONE_TYPE_MAP.get(None) # Retorna "Desconhecido" se phonenumbers não estiver disponível

    def _clean_number(self, phone_number: str) -> str:
        """Remove caracteres não-dígitos do número."""
        return re.sub(r'\D', '', phone_number)

    def _is_sequential_or_repeated(self, cleaned_number: str) -> bool:
        """Verifica se o número tem 4 ou mais dígitos sequenciais ou repetidos."""
        # Não aplicamos essa regra para números muito curtos, como códigos de serviço
        if len(cleaned_number) < 7: # Ajustado para ter um comprimento mínimo para esta regra
            return False

        # Verifica sequenciais (ex: 1234, 5432)
        for i in range(len(cleaned_number) - 3):
            subset = cleaned_number[i:i+4]
            # Converte para int para comparação numérica
            if all(d.isdigit() for d in subset): # Garante que são dígitos antes de int()
                s0, s1, s2, s3 = int(subset[0]), int(subset[1]), int(subset[2]), int(subset[3])
                if (s0 + 1 == s1 and s1 + 1 == s2 and s2 + 1 == s3): # Crescente
                    return True
                if (s0 - 1 == s1 and s1 - 1 == s2 and s2 - 1 == s3): # Decrescente
                    return True

        # Verifica repetidos (ex: 1111, 8888)
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
                # Use country_code_hint for parsing if provided
                parsed_number = phonenumbers.parse(cleaned_number, country_code_hint.upper() if country_code_hint else None)
                
                if phonenumbers.is_possible_number(parsed_number):
                    # If possible and/or valid, format to E.164
                    return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
                else:
                    return cleaned_number # Fallback to cleaned for further checks
            except NumberParseException as e:
                logger.debug(f"Parsing error in phonenumbers for '{phone_number}': {e}")
                return cleaned_number
            except Exception as e:
                logger.error(f"Unexpected error in phonenumbers.parse for '{phone_number}': {e}", exc_info=True)
                return cleaned_number
        else:
            # Fallback for basic cleaning and formatting if phonenumbers is not available.
            if cleaned_number.startswith("+"):
                # Already in international format (or attempt), keep as is
                return cleaned_number

            # Try to add country code if hint is available and not starting with '+'
            if country_code_hint and country_code_hint.upper() in COUNTRY_CODE_HINT_TO_NUMBER:
                country_num_code = COUNTRY_CODE_HINT_TO_NUMBER[country_code_hint.upper()]
                
                # For Brazilian numbers that don't start with +55 and already have the DDD
                # Brazilian numbers are typically 10 or 11 digits (DD + NNNN-NNNN or DD + 9NNNN-NNNN)
                if country_code_hint.upper() == "BR" and (len(cleaned_number) == 10 or len(cleaned_number) == 11):
                    # Remove '0' initial if present (ex: 011...)
                    if cleaned_number.startswith("0") and len(cleaned_number) > 2:
                        cleaned_number = cleaned_number[1:]
                    
                    # If the number already has the DDD, add only the +55.
                    # If it already starts with the country code, leave as is.
                    if not cleaned_number.startswith(str(country_num_code)):
                        return f"+{country_num_code}{cleaned_number}"
                    return cleaned_number # Already looks like +55...
                elif not cleaned_number.startswith(str(country_num_code)):
                    # For other countries, just prepend the country code
                    return f"+{country_num_code}{cleaned_number}"
            
            return cleaned_number # Return the clean number if no specific rule applies

    async def validate(self, data: str, country_code_hint: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Implementação do método abstrato 'validate' para validação de números de telefone.
        Utiliza a lógica interna para validação com phonenumbers ou fallback.

        Args:
            data (str): O número de telefone a ser validado.
            country_code_hint (Optional[str]): Uma dica de código de país (ISO 3166-1 alpha-2, ex: "BR", "US").
            **kwargs: Argumentos adicionais que podem ser passados (atualmente não usados aqui).

        Returns:
            Dict[str, Any]: Um dicionário com os detalhes da validação.
        """
        phone_number = data # 'data' é o número de telefone
        
        # Inicializa `details` com os campos adicionais
        details = {
            "input_original": phone_number,
            "country_hint_used": country_code_hint.upper() if country_code_hint else None,
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
                business_rule_applied={"code": VAL_PHN003, "type": "phone"}
            )

        # 1. Normaliza o número de telefone
        normalized_number = self._normalize_phone_number(phone_number, country_code_hint)
        
        if not normalized_number:
            return self._format_result(
                is_valid=False,
                dado_normalizado=None,
                mensagem="Número de telefone vazio após limpeza ou não contém dígitos válidos.",
                details=details,
                business_rule_applied={"code": VAL_PHN003, "type": "phone"}
            )
        
        # Extrai apenas dígitos para a verificação de sequencial/repetido e fallback rules
        digits_only = self._clean_number(phone_number)
        
        # 2. Tenta validação com phonenumbers (preferencial)
        if PHONENUMBERS_AVAILABLE:
            try:
                parsed_number = phonenumbers.parse(normalized_number, country_code_hint.upper() if country_code_hint else None)
                details["phonenumbers_possible"] = phonenumbers.is_possible_number(parsed_number)
                details["phonenumbers_valid"] = phonenumbers.is_valid_number(parsed_number)
                details["country_code_detected"] = parsed_number.country_code
                details["national_number"] = parsed_number.national_number

                if details["phonenumbers_valid"]:
                    details["type_detected"] = self._get_phone_type_name_safe(parsed_number)
                    # Verifica padrões sequenciais/repetidos MESMO que phonenumbers considere válido
                    if self._is_sequential_or_repeated(self._clean_number(phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164))):
                        return self._format_result(
                            is_valid=False,
                            dado_normalizado=phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164),
                            mensagem="Número de telefone inválido: sequencial ou com dígitos repetidos (mesmo válido pelo phonenumbers).",
                            details=details,
                            business_rule_applied={"code": VAL_PHN013, "type": "phone"}
                        )
                    return self._format_result(
                        is_valid=True,
                        dado_normalizado=phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164),
                        mensagem="Número de telefone válido (via phonenumbers).",
                        details=details,
                        business_rule_applied={"code": VAL_PHN001, "type": "phone"}
                    )

                elif details["phonenumbers_possible"]:
                    # Se phonenumbers considera possível, mas não válido, passamos para as regras de fallback.
                    logger.debug(f"Phonenumbers considers '{normalized_number}' possible but not valid. Trying fallback rules.")
                    pass
                else:
                    # Se phonenumbers não considera nem possível, passamos para as regras de fallback.
                    logger.debug(f"Phonenumbers considers '{normalized_number}' not possible. Trying fallback rules.")
                    pass
                    
            except NumberParseException as e:
                logger.debug(f"NumberParseException for '{normalized_number}': {e}. Trying fallback.")
                pass
            except Exception as e:
                logger.error(f"Unexpected error in phonenumbers for '{normalized_number}': {e}", exc_info=True)
                pass
        else:
            logger.info("Biblioteca 'phonenumbers' não disponível. Usando validação de fallback.")

        
        ### Lógica de Fallback (Regras Internas)
        
        # Priorize a verificação de números de serviço/emergência (3 dígitos)
        if len(digits_only) == 3 and digits_only.isdigit():
            if digits_only in SERVICE_EMERGENCY_NUMBERS_BR:
                details["type_detected"] = "Emergência/Serviço BR"
                details["country_code_detected"] = 55 # Assumindo números de emergência BR
                try:
                    details["national_number"] = int(digits_only)
                except ValueError:
                    details["national_number"] = None
                return self._format_result(
                    is_valid=True,
                    dado_normalizado=digits_only,
                    mensagem=f"Número de serviço/emergência válido ({digits_only} via fallback).",
                    details=details,
                    business_rule_applied={"code": VAL_PHN016, "type": "phone"}
                )
            else:
                return self._format_result(
                    is_valid=False,
                    dado_normalizado=normalized_number,
                    mensagem="Número de 3 dígitos não reconhecido como serviço/emergência (via fallback).",
                    details=details,
                    business_rule_applied={"code": VAL_PHN020, "type": "phone"}
                )

        # Verifica sequencial/repetido ANTES de outras regras genéricas
        if self._is_sequential_or_repeated(digits_only):
            return self._format_result(
                is_valid=False,
                dado_normalizado=normalized_number,
                mensagem="Número de telefone inválido: sequencial ou com dígitos repetidos.",
                details=details,
                business_rule_applied={"code": VAL_PHN013, "type": "phone"}
            )

        # Fallback para números internacionais (se começa com '+')
        if normalized_number.startswith('+'):
            temp_number_without_plus = normalized_number[1:]
            
            # Tenta separar código de país e número nacional
            match = re.match(r'^(\d{1,4})(\d+)$', temp_number_without_plus)
            if match:
                country_code_str = match.group(1)
                national_number_part = match.group(2)

                # Comprimento típico de número nacional em E.164 (7 a 15 dígitos após o código do país)
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
                        business_rule_applied={"code": VAL_PHN014, "type": "phone"}
                    )
                else:
                    return self._format_result(
                        is_valid=False,
                        dado_normalizado=normalized_number,
                        mensagem="Número internacional com comprimento de dígitos inválido (via fallback).",
                        details=details,
                        business_rule_applied={"code": VAL_PHN015, "type": "phone"}
                    )
            else:
                return self._format_result(
                    is_valid=False,
                    dado_normalizado=normalized_number,
                    mensagem="Número internacional com formato básico não reconhecido (via fallback).",
                    details=details,
                    business_rule_applied={"code": VAL_PHN020, "type": "phone"}
                )

        # Fallback para números brasileiros (se country_code_hint é BR ou detectado como tal)
        is_br_hint = country_code_hint and country_code_hint.upper() == "BR"
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
                        business_rule_applied={"code": VAL_PHN011, "type": "phone"}
                    )
                else:
                    # Celular brasileiro (11 dígitos, começando com 9 após DDD)
                    if len(digits_only) == 11 and numero_principal.startswith('9'):
                        details["type_detected"] = "Celular BR"
                        details["country_code_detected"] = 55
                        try:
                            details["national_number"] = int(digits_only)
                        except ValueError:
                            details["national_number"] = None
                        return self._format_result(
                            is_valid=True,
                            dado_normalizado=f"+55{digits_only}", # Garante E.164 para BR
                            mensagem="Número de telefone celular brasileiro válido (via fallback).",
                            details=details,
                            business_rule_applied={"code": VAL_PHN010, "type": "phone"}
                        )
                    # Fixo brasileiro (10 dígitos, DDD + 8 dígitos)
                    elif len(digits_only) == 10 and numero_principal[0] in ('2', '3', '4', '5'): # Prefixos comuns para fixo
                        details["type_detected"] = "Fixo BR"
                        details["country_code_detected"] = 55
                        try:
                            details["national_number"] = int(digits_only)
                        except ValueError:
                            details["national_number"] = None
                        return self._format_result(
                            is_valid=True,
                            dado_normalizado=f"+55{digits_only}", # Garante E.164 para BR
                            mensagem="Número de telefone fixo brasileiro válido (via fallback).",
                            details=details,
                            business_rule_applied={"code": VAL_PHN010, "type": "phone"}
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
                            business_rule_applied={"code": VAL_PHN012, "type": "phone"}
                        )
            else: # Comprimento inválido para número brasileiro
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
                    business_rule_applied={"code": VAL_PHN012, "type": "phone"} # Reutilizado para comprimento BR inválido
                )
            
        # Caso geral: o número não se encaixa em nenhuma regra específica
        return self._format_result(
            is_valid=False,
            dado_normalizado=normalized_number,
            mensagem="Número de telefone com formato ou comprimento não reconhecido (via fallback).",
            details=details,
            business_rule_applied={"code": VAL_PHN020, "type": "phone"}
        )