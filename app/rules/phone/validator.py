# app/rules/phone/validator.py

import re
import logging
from typing import Optional, Dict, Any

# Configuração de logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Configuração do "Database" Interno (regras em memória) ---

# Conjunto de DDDs Válidos para buscas eficientes (O(1)) no Brasil
DDD_VALIDOS_BR = {
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "21", "22", "24",
    "27", "28", "31", "32", "33", "34", "35", "37", "38", "41", "42", "43",
    "44", "45", "46", "47", "48", "49", "51", "53", "54", "55", "61", "62",
    "63", "64", "65", "66", "67", "68", "69", "71", "73", "74", "75", "77",
    "79", "81", "82", "83", "84", "85", "86", "87", "88", "89", "91", "92",
    "93", "94", "95", "96", "97", "98", "99"
}

# Códigos de Regra específicos para telefone
RNT_VALID_SYNTAX = "RNT001"            # Validação de sintaxe básica (phonenumbers ou regex)
RNT_VALID_GEO = "RNT002"               # Validação geográfica (phonenumbers)
RNT_POSSIBLE = "RNT003"                # Número possível, mas não válido (phonenumbers)
RNT_FALLBACK_BR_VALID = "RNT004"       # Validação de fallback para números BR (válido)
RNT_FALLBACK_INTERNATIONAL_VALID = "RNT005" # Validação de fallback para números internacionais (válido)
RNT_INVALID_FORMAT = "RNT006"          # Formato geral inválido (erros de parsing, regex falha)
RNT_FALLBACK_BR_INVALID_DDD = "RNT007" # Fallback: DDD inválido para BR
RNT_FALLBACK_BR_INVALID_LEN = "RNT008" # Fallback: Comprimento inválido para BR
RNT_PHONENUMBERS_PARSE_ERROR = "RNT009" # Erro específico de parsing do phonenumbers
RNT_PHONENUMBERS_UNEXPECTED_ERROR = "RNT010" # Erro inesperado do phonenumbers

# --- Configuração e carregamento da biblioteca phonenumbers ---

PHONENUMBERS_AVAILABLE = True
try:
    import phonenumbers
    from phonenumbers import PhoneNumberType, NumberParseException
    from phonenumbers.phonenumberutil import CountryCodeSource # Importa para obter códigos de país

    # Mapeamento de tipos de telefone do phonenumbers para nomes amigáveis em português
    PHONE_TYPE_MAP = {
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
    }

    def _get_phone_type_name_safe(parsed_number_obj) -> str:
        """
        Função auxiliar para obter o nome amigável do tipo de telefone.
        Garante que mesmo que o type não esteja no mapeamento, retorne algo útil.
        """
        num_type = phonenumbers.get_number_type(parsed_number_obj)
        return PHONE_TYPE_MAP.get(num_type, f"Tipo Desconhecido ({num_type.name})")

except ImportError:
    PHONENUMBERS_AVAILABLE = False
    logger.warning("A biblioteca 'phonenumbers' não está instalada. A validação de telefone será menos precisa e dependerá de regras de fallback.")
except Exception as e:
    PHONENUMBERS_AVAILABLE = False
    logger.error(f"Erro inesperado ao carregar ou configurar phonenumbers: {e}. Desativando phonenumbers.")


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
    - rule_code (str): Código da regra de negócio que foi aplicada.
    """

    def __init__(self):
        pass

    def validate(self, phone_number: str, country_code_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Valida um número de telefone aplicando uma sequência de regras:
        1. Normalização do número.
        2. Validação com phonenumbers (se disponível e aplicável).
        3. Validação de fallback usando regras em memória (DDDs, padrões básicos).

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
            "source": "inicial", # Será atualizado durante o processo
            "details": {
                "input_original": phone_number,
                "country_hint_used": country_code_hint,
                "type_detected": None,
                "phonenumbers_possible": False,
                "phonenumbers_valid": False,
                "international_format_generated": False, # Indica se o E.164 foi gerado
            },
            "rule_code": RNT_INVALID_FORMAT
        }

        # 1. Normaliza o número de telefone (tenta E.164 via phonenumbers primeiro)
        normalized_number = self._normalize_phone_number(phone_number, country_code_hint)
        result["cleaned_data"] = normalized_number
        if normalized_number.startswith('+') and len(normalized_number) > 1: # Se foi formatado para internacional
             result["details"]["international_format_generated"] = True

        if not normalized_number:
            result["message"] = "Número de telefone vazio ou não contém dígitos válidos."
            result["rule_code"] = RNT_INVALID_FORMAT
            return result

        # 2. Tenta validação com phonenumbers (preferencial)
        if PHONENUMBERS_AVAILABLE:
            try:
                # O phonenumbers.parse já tenta adivinhar a região se não há country_code_hint
                # ou se o número começa com '+', mas a dica ajuda em números locais sem prefixo.
                parsed_number = phonenumbers.parse(normalized_number, country_code_hint)
                result["source"] = "phonenumbers"
                
                result["details"]["phonenumbers_possible"] = phonenumbers.is_possible_number(parsed_number)
                result["details"]["phonenumbers_valid"] = phonenumbers.is_valid_number(parsed_number)
                result["details"]["country_code_detected"] = parsed_number.country_code if result["details"]["phonenumbers_valid"] else None
                result["details"]["national_number"] = parsed_number.national_number if result["details"]["phonenumbers_valid"] else None

                if result["details"]["phonenumbers_valid"]:
                    result["is_valid"] = True
                    result["details"]["type_detected"] = _get_phone_type_name_safe(parsed_number)
                    
                    # Verifica validade para a região, se uma dica foi fornecida
                    if country_code_hint and not phonenumbers.is_valid_number_for_region(parsed_number, country_code_hint):
                        result["message"] = f"Número válido globalmente, mas não para a região '{country_code_hint}'."
                        result["rule_code"] = RNT_VALID_GEO
                    else:
                        result["message"] = "Número de telefone válido (via phonenumbers)."
                        result["rule_code"] = RNT_VALID_SYNTAX
                    
                    # Retorna imediatamente se válido pelo phonenumbers
                    return result

                elif result["details"]["phonenumbers_possible"]:
                    result["is_valid"] = False
                    result["message"] = "Número de telefone parece possível, mas não é válido (via phonenumbers)."
                    result["rule_code"] = RNT_POSSIBLE
                    # Não retorna aqui, continua para o fallback, pois "possível" não é "válido"
                else:
                    result["is_valid"] = False
                    result["message"] = "Número de telefone inválido para o padrão internacional (via phonenumbers)."
                    result["rule_code"] = RNT_INVALID_FORMAT
                    # Não retorna aqui, continua para o fallback
                    
            except NumberParseException as e:
                logger.debug(f"Erro de parsing phonenumbers para '{normalized_number}': {e}")
                result["message"] = f"Erro de parsing do número de telefone: {e.args[0]}. Tentando fallback."
                result["is_valid"] = False
                result["rule_code"] = RNT_PHONENUMBERS_PARSE_ERROR
            except Exception as e:
                logger.error(f"Erro inesperado no phonenumbers para '{normalized_number}': {e}", exc_info=True)
                result["message"] = f"Erro inesperado durante a validação phonenumbers: {e}. Tentando fallback."
                result["is_valid"] = False
                result["rule_code"] = RNT_PHONENUMBERS_UNEXPECTED_ERROR
        
        # 3. Validação de Fallback (se phonenumbers não foi usado, falhou ou o número não é internacional completo)
        # Esta camada tenta validar números com base em regras mais simples, úteis para formatos locais
        # ou quando phonenumbers não está disponível/falha.
        
        # Se phonenumbers já marcou como válido, não sobrescrever com fallback
        if result["is_valid"] and result["source"] == "phonenumbers":
            return result

        result["source"] = "fallback" # Agora a origem é fallback

        # Fallback para números internacionais (já formatados com '+')
        if normalized_number.startswith('+'):
            # Remove o '+' para verificar o comprimento do número com o código do país
            number_without_plus = normalized_number[1:]
            if 7 <= len(number_without_plus) <= 15: # Comprimento típico de números internacionais
                result["is_valid"] = True
                result["message"] = "Número internacional válido (formato E.164 básico via fallback)."
                result["details"]["type_detected"] = "Internacional Básico"
                result["rule_code"] = RNT_FALLBACK_INTERNATIONAL_VALID
            else:
                result["is_valid"] = False
                result["message"] = "Número internacional com comprimento de dígitos inválido (via fallback)."
                result["rule_code"] = RNT_INVALID_FORMAT
        
        # Fallback para números brasileiros (sem prefixo '+' ou apenas dígitos)
        elif 10 <= len(normalized_number) <= 11: # Números brasileiros (DDDNnnnnn ou DDDNNnnnn)
            ddd = normalized_number[:2]
            if ddd not in DDD_VALIDOS_BR:
                result["is_valid"] = False
                result["message"] = f"DDD '{ddd}' inválido para o Brasil (via fallback)."
                result["rule_code"] = RNT_FALLBACK_BR_INVALID_DDD
            else:
                numero_principal = normalized_number[2:]
                # Celular brasileiro (9 dígitos, começando com 9)
                if len(numero_principal) == 9 and numero_principal.startswith('9'):
                    result["is_valid"] = True
                    result["message"] = "Número de telefone celular brasileiro válido (via fallback)."
                    result["details"]["type_detected"] = "Celular BR"
                    result["rule_code"] = RNT_FALLBACK_BR_VALID
                # Fixo brasileiro (8 dígitos, começando com 2,3,4,5)
                elif len(numero_principal) == 8 and numero_principal[0] in ('2', '3', '4', '5'):
                    result["is_valid"] = True
                    result["message"] = "Número de telefone fixo brasileiro válido (via fallback)."
                    result["details"]["type_detected"] = "Fixo BR"
                    result["rule_code"] = RNT_FALLBACK_BR_VALID
                else:
                    result["is_valid"] = False
                    result["message"] = "Número de telefone brasileiro com estrutura inválida (via fallback)."
                    result["rule_code"] = RNT_FALLBACK_BR_INVALID_LEN # Mais específico
        
        elif len(normalized_number) == 3: # Números de serviço/emergência (ex: 190, 192)
            result["is_valid"] = True
            result["message"] = "Número de serviço/emergência válido (3 dígitos via fallback)."
            result["details"]["type_detected"] = "Emergência/Serviço"
            result["rule_code"] = RNT_FALLBACK_BR_VALID # Considera válido para BR
        
        else:
            result["is_valid"] = False
            result["message"] = "Número de telefone com formato ou comprimento não reconhecido (via fallback)."
            result["rule_code"] = RNT_INVALID_FORMAT
            
        return result

    def _normalize_phone_number(self, phone_number: str, country_code_hint: Optional[str] = None) -> str:
        """
        Limpa o número de telefone removendo caracteres não-dígitos e tenta
        formatá-lo para E.164 se possível, usando phonenumbers ou uma heurística simples.
        """
        if not phone_number:
            return ""

        # Remove todos os caracteres não-dígitos, exceto o '+' inicial
        if phone_number.startswith('+'):
            cleaned_number = '+' + ''.join(filter(str.isdigit, phone_number[1:]))
        else:
            cleaned_number = ''.join(filter(str.isdigit, phone_number))

        if not cleaned_number:
            return "" # Retorna vazio se não houver dígitos

        # Tenta formatar para E.164 usando phonenumbers, se disponível
        if PHONENUMBERS_AVAILABLE:
            try:
                # Primeiro, tenta parsear o número limpo como está
                # Se for um número internacional com '+', tenta parsear sem dica.
                # Se não tem '+', tenta com a dica de país.
                if cleaned_number.startswith('+'):
                    parsed = phonenumbers.parse(cleaned_number, None)
                elif country_code_hint:
                    parsed = phonenumbers.parse(cleaned_number, country_code_hint.upper())
                else:
                    # Se não tem '+' e não tem hint, tenta com 'BR' como default para a normalização inicial
                    parsed = phonenumbers.parse(cleaned_number, "BR") 

                # Se o parse resultou em um número possível/válido, formatar para E.164
                if phonenumbers.is_valid_number(parsed) or phonenumbers.is_possible_number(parsed):
                    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except NumberParseException:
                logger.debug(f"Normalization failed for '{cleaned_number}' with phonenumbers. Falling back.")
                pass # Ignora erros de parse e continua para o fallback de normalização
            except Exception as e:
                logger.warning(f"Unexpected error during phonenumbers normalization for '{cleaned_number}': {e}")
                pass # Continua para o fallback de normalização
        
        # Fallback de normalização: garante o '+' para validação posterior se for o caso
        # Esta lógica só será executada se phonenumbers não estiver disponível ou falhou na normalização
        if not cleaned_number.startswith('+'):
            if country_code_hint:
                # Tenta obter o código de país a partir da dica da região via phonenumbers
                if PHONENUMBERS_AVAILABLE:
                    try:
                        country_code = phonenumbers.CountryCodeSource.get_country_code_for_region(country_code_hint.upper())
                        if country_code:
                            return f'+{country_code}{cleaned_number}'
                    except Exception:
                        pass # Falha ao obter o código, segue para heurísticas
                
                # Heurísticas mais simples se phonenumbers não ajudou ou não está disponível
                if country_code_hint.upper() == 'BR' and (len(cleaned_number) == 10 or len(cleaned_number) == 11):
                    return '+55' + cleaned_number
                elif country_code_hint.upper() == 'US' and len(cleaned_number) == 10: 
                    return '+1' + cleaned_number
                # Poderia ter mais mapeamentos de países aqui ou um mecanismo mais genérico

            # Último recurso se não há hint específico ou se as heurísticas falharam:
            # Se é um número longo que parece um número de telefone mas não tem prefixo internacional,
            # adiciona '+' genericamente. Isso é um risco e deve ser usado com cautela.
            if len(cleaned_number) >= 7: # Mínimo de dígitos para ser um número de telefone
                logger.debug(f"Adding '+' prefix as last resort for '{cleaned_number}'")
                return '+' + cleaned_number
            
        return cleaned_number # Retorna o número limpo como está se nenhum padrão foi aplicado