# app/rules/phone/validator.py

import re
import logging
from typing import Optional, Dict, Any

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
VAL_PHN001 = "VAL_PHN001"   # Válido e possível via phonenumbers
VAL_PHN002 = "VAL_PHN002"   # Inválido via phonenumbers
VAL_PHN003 = "VAL_PHN003"   # Input vazio ou tipo errado
VAL_PHN004 = "VAL_PHN004"   # Possível mas não válido via phonenumbers
VAL_PHN005 = "VAL_PHN005"   # Erro de parsing do phonenumbers
VAL_PHN006 = "VAL_PHN006"   # Erro inesperado do phonenumbers
VAL_PHN010 = "VAL_PHN010"   # Validação BR via fallback: Celular/Fixo válido
VAL_PHN011 = "VAL_PHN011"   # Validação BR via fallback: DDD inválido
VAL_PHN012 = "VAL_PHN012"   # Validação BR via fallback: Comprimento/formato inválido para BR
VAL_PHN013 = "VAL_PHN013"   # Validação: Número sequencial/repetido
VAL_PHN014 = "VAL_PHN014"   # Validação internacional via fallback: Válido (E.164 básico)
VAL_PHN015 = "VAL_PHN015"   # Validação internacional via fallback: Comprimento inválido
VAL_PHN016 = "VAL_PHN016"   # Validação de serviço/emergência (ex: 190, 192)
VAL_PHN020 = "VAL_PHN020"   # Formato geral não reconhecido (fallback)

## Configuração e carregamento da biblioteca phonenumbers

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
        PhoneNumberType.SHORT_CODE: "Código Curto",
        PhoneNumberType.STANDARD_RATE: "Tarifa Padrão",
        PhoneNumberType.EMERGENCY: "Emergência",
        PhoneNumberType.NO_TYPE: "Sem Tipo",
    })

except ImportError:
    PHONENUMBERS_AVAILABLE = False
    logger.warning("A biblioteca 'phonenumbers' não está instalada. A validação de telefone será menos precisa e dependerá de regras de fallback.")
except Exception as e:
    PHONENUMBERS_AVAILABLE = False
    logger.error(f"Erro inesperado ao carregar ou configurar phonenumbers: {e}. Desativando phonenumbers.")

# Função auxiliar para obter o nome amigável do tipo de telefone (acessível mesmo sem phonenumbers)
def _get_phone_type_name_safe(parsed_number_obj) -> str:
    """
    Função auxiliar para obter o nome amigável do tipo de telefone.
    Garante que mesmo que o type não esteja no mapeamento, retorne algo útil.
    """
    if PHONENUMBERS_AVAILABLE and parsed_number_obj:
        num_type = phonenumbers.get_number_type(parsed_number_obj)
        return PHONE_TYPE_MAP.get(num_type, f"Tipo Desconhecido ({num_type.name})")
    return PHONE_TYPE_MAP.get(None) # Retorna "Desconhecido" se phonenumbers não estiver disponível

class PhoneValidator:
    """
    Validador de números de telefone que utiliza a biblioteca phonenumbers
    para validação robusta e inclui regras de fallback (em memória) para
    casos onde phonenumbers não é aplicável ou não está disponível.

    O método `validate` retorna um dicionário padronizado com as chaves:
    - is_valid (bool): Se o dado é válido.
    - cleaned_data (str): O dado normalizado (ex: E.164).
    - message (str): Mensagem explicativa do resultado.
    - source (str): A fonte da validação (e.g., "phonenumbers", "fallback_br").
    - details (dict): Detalhes específicos da validação.
    - validation_code (str): Código da regra de VALIDAÇÃO que foi aplicada.
    """

    def __init__(self):
        pass

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
                if country_code_hint:
                    parsed_number = phonenumbers.parse(cleaned_number, country_code_hint.upper())
                else:
                    parsed_number = phonenumbers.parse(cleaned_number)

                if phonenumbers.is_possible_number(parsed_number):
                    # Se for possível e/ou válido, formata para E.164
                    return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
                else:
                    return cleaned_number # Fallback to cleaned for further checks
            except NumberParseException:
                logger.debug(f"Erro de parsing phonenumbers em _normalize_phone_number para '{phone_number}': {NumberParseException}")
                return cleaned_number
            except Exception as e:
                logger.error(f"Erro inesperado em phonenumbers.parse em _normalize_phone_number para '{phone_number}': {e}", exc_info=True)
                return cleaned_number
        else:
            # Fallback para limpeza e formatação básica se phonenumbers não está disponível.
            if cleaned_number.startswith("+"):
                # Já está em formato internacional (ou tentativa), manter como está
                return cleaned_number

            # Tenta adicionar código de país se houver hint e não começar com '+'
            if country_code_hint and country_code_hint.upper() in COUNTRY_CODE_HINT_TO_NUMBER:
                country_num_code = COUNTRY_CODE_HINT_TO_NUMBER[country_code_hint.upper()]
                # Para números brasileiros que não começam com +55 e já tem o DDD
                if country_code_hint.upper() == "BR" and len(cleaned_number) >= 10:
                    # Remove '0' inicial se for presente (ex: 011...)
                    if cleaned_number.startswith("0") and len(cleaned_number) > 2:
                        cleaned_number = cleaned_number[1:]
                    
                    # Se o número já tem o DDD, adicione apenas o +55.
                    # Se já começa com o código do país, deixe como está.
                    if not cleaned_number.startswith(str(country_num_code)):
                        return f"+{country_num_code}{cleaned_number}"
                    return cleaned_number # Já está ok (e.g., 5511...)
                elif not cleaned_number.startswith(str(country_num_code)):
                    # Para outros países, apenas adiciona o código do país
                    return f"+{country_num_code}{cleaned_number}"
            
            return cleaned_number # Retorna o número limpo se nenhuma regra se aplica

    async def validate_phone(self, phone_number: str, country_code_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Valida um número de telefone aplicando uma sequência de regras:
        1. Normalização do número.
        2. Validação com phonenumbers (se disponível e aplicável).
        3. Validação de fallback usando regras em memória (DDDs, padrões básicos, sequenciais/repetidos).

        Args:
            phone_number (str): O número de telefone a ser validado.
            country_code_hint (Optional[str]): Uma dica de código de país (ISO 3166-1 alpha-2, ex: "BR", "US").

        Returns:
            Dict[str, Any]: Um dicionário com os detalhes da validação.
        """
        result = {
            "is_valid": False,
            "cleaned_data": "",
            "message": "Falha na validação inicial.",
            "source": "inicial",
            "details": {
                "input_original": phone_number,
                "country_hint_used": country_code_hint.upper() if country_code_hint else None,
                "type_detected": None,
                "phonenumbers_possible": False,
                "phonenumbers_valid": False,
                "international_format_generated": False,
                "country_code_detected": None,
                "national_number": None,
            },
            "validation_code": VAL_PHN020
        }

        if not phone_number or not isinstance(phone_number, str):
            result["message"] = "Número de telefone deve ser uma string não vazia."
            result["validation_code"] = VAL_PHN003
            return result

        # 1. Normaliza o número de telefone
        normalized_number = self._normalize_phone_number(phone_number, country_code_hint)
        result["cleaned_data"] = normalized_number

        if not normalized_number:
            result["message"] = "Número de telefone vazio após limpeza ou não contém dígitos válidos."
            result["validation_code"] = VAL_PHN003
            return result
        
        # Extrai apenas dígitos para a verificação de sequencial/repetido
        digits_only = self._clean_number(phone_number)
        
        # 2. Tenta validação com phonenumbers (preferencial)
        if PHONENUMBERS_AVAILABLE:
            try:
                parsed_number = phonenumbers.parse(normalized_number, country_code_hint.upper() if country_code_hint else None)
                result["source"] = "phonenumbers"
                
                result["details"]["phonenumbers_possible"] = phonenumbers.is_possible_number(parsed_number)
                result["details"]["phonenumbers_valid"] = phonenumbers.is_valid_number(parsed_number)
                result["details"]["country_code_detected"] = parsed_number.country_code
                result["details"]["national_number"] = parsed_number.national_number

                if result["details"]["phonenumbers_valid"]:
                    result["is_valid"] = True
                    result["details"]["type_detected"] = _get_phone_type_name_safe(parsed_number)
                    result["message"] = "Número de telefone válido (via phonenumbers)."
                    result["validation_code"] = VAL_PHN001
                    result["cleaned_data"] = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
                    return result

                elif result["details"]["phonenumbers_possible"]:
                    result["is_valid"] = False
                    result["message"] = "Número de telefone parece possível, mas não é válido (via phonenumbers)."
                    result["validation_code"] = VAL_PHN004
                    # Fall through to fallback rules if phonenumbers deems it only possible
                else:
                    result["is_valid"] = False
                    result["message"] = "Número de telefone inválido para o padrão internacional (via phonenumbers)."
                    result["validation_code"] = VAL_PHN002
                    # Fall through to fallback rules
                    
            except NumberParseException as e:
                logger.debug(f"Erro de parsing phonenumbers para '{normalized_number}': {e}. Tentando fallback.")
                result["message"] = f"Erro de parsing do número de telefone: {e.args[0]}. Tentando fallback."
                result["is_valid"] = False
                result["validation_code"] = VAL_PHN005
            except Exception as e:
                logger.error(f"Erro inesperado no phonenumbers para '{normalized_number}': {e}", exc_info=True)
                result["message"] = f"Erro inesperado durante a validação phonenumbers: {e}. Tentando fallback."
                result["is_valid"] = False
                result["validation_code"] = VAL_PHN006
        else:
            result["message"] = "Biblioteca 'phonenumbers' não disponível. Usando validação de fallback."

        result["source"] = "fallback"

        # **Lógica de Fallback:**

        # Priorize a verificação de números de serviço/emergência (3 dígitos)
        if len(digits_only) == 3 and digits_only.isdigit():
            if digits_only in SERVICE_EMERGENCY_NUMBERS_BR:
                result["is_valid"] = True
                result["message"] = f"Número de serviço/emergência válido ({digits_only} via fallback)."
                result["details"]["type_detected"] = "Emergência/Serviço BR"
                result["validation_code"] = VAL_PHN016
                result["details"]["country_code_detected"] = 55
                try:
                    result["details"]["national_number"] = int(digits_only)
                except ValueError:
                    result["details"]["national_number"] = None
            else:
                result["is_valid"] = False
                result["message"] = "Número de 3 dígitos não reconhecido como serviço/emergência (via fallback)."
                result["validation_code"] = VAL_PHN020
            return result

        # Verifica sequencial/repetido ANTES de outras regras genéricas
        # Aplica a verificação de sequencial/repetido ao número *limpo*, não ao E.164 formatado
        if self._is_sequential_or_repeated(digits_only):
            result["is_valid"] = False
            result["message"] = "Número de telefone inválido: sequencial ou com dígitos repetidos."
            result["validation_code"] = VAL_PHN013
            return result

        # Fallback para números internacionais (se começa com '+')
        if normalized_number.startswith('+'):
            temp_number_without_plus = normalized_number[1:]
            
            # Tenta separar código de país e número nacional
            match = re.match(r'^(\d{1,4})(\d+)$', temp_number_without_plus)
            if match:
                country_code_str = match.group(1)
                national_number_part = match.group(2)

                if 7 <= len(national_number_part) <= 15: # Comprimento típico
                    result["is_valid"] = True
                    result["message"] = "Número internacional válido (formato E.164 básico via fallback)."
                    result["details"]["type_detected"] = "Internacional Básico"
                    result["validation_code"] = VAL_PHN014
                    try:
                        result["details"]["country_code_detected"] = int(country_code_str)
                    except ValueError:
                        result["details"]["country_code_detected"] = None
                    try:
                        result["details"]["national_number"] = int(national_number_part)
                    except ValueError:
                        result["details"]["national_number"] = None
                else:
                    result["is_valid"] = False
                    result["message"] = "Número internacional com comprimento de dígitos inválido (via fallback)."
                    result["validation_code"] = VAL_PHN015
            else:
                result["is_valid"] = False
                result["message"] = "Número internacional com formato básico não reconhecido (via fallback)."
                result["validation_code"] = VAL_PHN020
            
            return result

        # Fallback para números brasileiros (se country_code_hint é BR ou detectado como tal)
        # Use digits_only para as regras de comprimento e DDD brasileiras
        if country_code_hint and country_code_hint.upper() == "BR" or \
           (len(digits_only) >= 10 and digits_only.isdigit() and digits_only[:2] in DDD_VALIDOS_BR):

            if 10 <= len(digits_only) <= 11:
                ddd = digits_only[:2]
                numero_principal = digits_only[2:]

                if not self._is_brazilian_ddd_valid(ddd):
                    result["is_valid"] = False
                    result["message"] = f"DDD '{ddd}' inválido para o Brasil (via fallback)."
                    result["validation_code"] = VAL_PHN011
                else:
                    # Celular brasileiro (11 dígitos, começando com 9 após DDD)
                    if len(digits_only) == 11 and numero_principal.startswith('9'):
                        result["is_valid"] = True
                        result["message"] = "Número de telefone celular brasileiro válido (via fallback)."
                        result["details"]["type_detected"] = "Celular BR"
                        result["validation_code"] = VAL_PHN010
                        result["cleaned_data"] = f"+55{digits_only}" # Garante E.164 para BR
                    # Fixo brasileiro (10 dígitos, DDD + 8 dígitos)
                    elif len(digits_only) == 10 and numero_principal[0] in ('2', '3', '4', '5'):
                        result["is_valid"] = True
                        result["message"] = "Número de telefone fixo brasileiro válido (via fallback)."
                        result["details"]["type_detected"] = "Fixo BR"
                        result["validation_code"] = VAL_PHN010
                        result["cleaned_data"] = f"+55{digits_only}" # Garante E.164 para BR
                    else:
                        result["is_valid"] = False
                        result["message"] = "Número de telefone brasileiro com estrutura inválida (DDD + número)."
                        result["validation_code"] = VAL_PHN012
                # Preencher country_code_detected e national_number para BR
                if result["is_valid"] or result["validation_code"] == VAL_PHN011:
                    result["details"]["country_code_detected"] = 55
                    try:
                        result["details"]["national_number"] = int(digits_only)
                    except ValueError:
                        result["details"]["national_number"] = None
            else: # Comprimento inválido para número brasileiro
                result["is_valid"] = False
                result["message"] = "Número de telefone brasileiro com comprimento inválido (10 ou 11 dígitos esperados)."
                result["validation_code"] = VAL_PHN012 # Reutilizado para comprimento BR inválido
                result["details"]["country_code_detected"] = 55 if ddd else None
                try:
                    result["details"]["national_number"] = int(digits_only)
                except ValueError:
                    result["details"]["national_number"] = None
            return result
        
        # Caso geral: número não se encaixou em nenhuma regra específica
        result["is_valid"] = False
        result["message"] = "Número de telefone com formato ou comprimento não reconhecido (via fallback)."
        result["validation_code"] = VAL_PHN020
        return result