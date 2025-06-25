# app/rules/phone/validator.py

import re
import logging
from typing import Dict, Any, Optional, Union
from app.rules.base import BaseValidator

# Importação condicional da biblioteca phonenumbers
PHONENUMBERS_AVAILABLE = True
try:
    import phonenumbers
    from phonenumbers import PhoneNumberType # Importar para usar os tipos
except ImportError:
    PHONENUMBERS_AVAILABLE = False
    logging.warning("A biblioteca 'phonenumbers' não está instalada. A validação de telefone será básica (apenas regex).")
except Exception as e:
    PHONENUMBERS_AVAILABLE = False
    logging.error(f"Erro inesperado ao carregar phonenumbers: {e}. Desativando validação avançada.", exc_info=True)


logger = logging.getLogger(__name__)

# Códigos de Regra específicos para validação de Telefone (Padronização RN_TELxxx)
class PhoneRuleCodes:
    RN_TEL001 = "RN_TEL001" # Telefone válido e reconhecido (formato e tipo)
    RN_TEL002 = "RN_TEL002" # Formato de telefone inválido (não passa regex/lib)
    RN_TEL003 = "RN_TEL003" # Telefone com código de país ou DDD inválido/não correspondente
    RN_TEL004 = "RN_TEL004" # Telefone não encontrado em base cadastral (simulado)
    RN_TEL005 = "RN_TEL005" # Telefone ativo, mas sinalizado como fraude/risco na base cadastral (simulado)
    RN_TEL006 = "RN_TEL006" # Tipo de telefone inconsistente (ex: fixo com numeração de celular)
    RN_TEL007 = "RN_TEL007" # Telefone é de serviço premium/spam
    RN_TEL008 = "RN_TEL008" # Input vazio ou tipo inválido (não string, ou string vazia)
    RN_TEL009 = "RN_TEL009" # Falha interna na validação (erro de biblioteca, etc.)
    RN_TEL010 = "RN_TEL010" # Tipo de telefone desconhecido pela biblioteca

class PhoneValidator(BaseValidator):
    """
    Validador para números de telefone.
    Utiliza a biblioteca 'phonenumbers' para validação robusta
    e inclui validações adicionais (regex, simulação de base cadastral).
    """

    def __init__(self):
        super().__init__(origin_name="phone_validator")
        logger.info("PhoneValidator inicializado.")
        # Simulação de uma base de dados de clientes para verificação de status
        self.simulated_customer_database = {
            "+5511983802243": {"is_active": True, "is_fraud_risk": False, "customer_name": "João Silva"},
            "+5516994130828": {"is_active": True, "is_fraud_risk": False, "customer_name": "Maria Oliveira"},
            "+5516983974673": {"is_active": True, "is_fraud_risk": True, "customer_name": "Pedro Souza"}, # Exemplo de risco de fraude
            "+12025550100": {"is_active": False, "is_fraud_risk": False, "customer_name": "Alice Wonderland"}, # Exemplo inativo
        }
        # Mapeamento para nomes de tipo de telefone, caso a biblioteca não forneça um método direto
        self._phone_type_names = {
            PhoneNumberType.FIXED_LINE: "FIXED_LINE",
            PhoneNumberType.MOBILE: "MOBILE",
            PhoneNumberType.FIXED_LINE_OR_MOBILE: "FIXED_OR_MOBILE",
            PhoneNumberType.TOLL_FREE: "TOLL_FREE",
            PhoneNumberType.PREMIUM_RATE: "PREMIUM_RATE",
            PhoneNumberType.SHARED_COST: "SHARED_COST",
            PhoneNumberType.VOIP: "VOIP",
            PhoneNumberType.PERSONAL_NUMBER: "PERSONAL_NUMBER",
            PhoneNumberType.PAGER: "PAGER",
            PhoneNumberType.UAN: "UAN",
            PhoneNumberType.VOICEMAIL: "VOICEMAIL",
            PhoneNumberType.UNKNOWN: "UNKNOWN",
        }


    async def validate(self, data: Any, client_identifier: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Valida um número de telefone, aplicando diversas regras e consultando
        uma base de dados cadastral simulada.

        Args:
            data (Any): O número de telefone a ser validado. Esperado string ou PhoneValidationData.
            client_identifier (Optional[str]): Identificador do cliente, para logging e regras.
            **kwargs: Parâmetros adicionais.

        Returns:
            Dict[str, Any]: Dicionário com o resultado da validação padronizado.
        """
        phone_number_str = ""
        country_hint = "BR" # Default para Brasil

        if isinstance(data, str):
            phone_number_str = data
        elif isinstance(data, dict):
            phone_number_str = data.get("phone_number", "")
            country_hint = data.get("country_hint", "BR")
        elif hasattr(data, 'phone_number'): # Se for um modelo Pydantic PhoneValidationData
            phone_number_str = data.phone_number
            country_hint = data.country_hint if hasattr(data, 'country_hint') else "BR"
        else:
            return self._format_result(
                is_valid=False,
                dado_original=data, # Passa dado_original
                dado_normalizado=None,
                mensagem="Input de telefone vazio ou tipo inválido. Esperado string ou dicionário/Pydantic model com 'phone_number'.",
                details={"input_original": data, "reason": "invalid_input_type"},
                business_rule_applied={"code": PhoneRuleCodes.RN_TEL008, "type": "Telefone - Validação Primária", "name": "Input Vazio ou Inválido"}
            )

        if not phone_number_str.strip():
            return self._format_result(
                is_valid=False,
                dado_original=phone_number_str, # Passa dado_original
                dado_normalizado=None,
                mensagem="Número de telefone vazio.",
                details={"input_original": phone_number_str, "reason": "empty_string"},
                business_rule_applied={"code": PhoneRuleCodes.RN_TEL008, "type": "Telefone - Validação Primária", "name": "Número de Telefone Vazio"}
            )

        normalized_phone = phone_number_str.strip()
        is_valid = False
        message = "Número de telefone inválido."
        business_rule_code = PhoneRuleCodes.RN_TEL002 # Default
        details = {
            "input_original": phone_number_str,
            "country_hint": country_hint,
            "parsed_successfully": False,
            "is_possible": False,
            "is_valid_number": False,
            "phone_type": "UNKNOWN",
            "country_code": None,
            "national_number": None,
            "international_format": None,
            "simulated_db_status": None,
            "is_fraud_risk": False,
            "customer_name": None,
            "reason": []
        }

        parsed_phone = None
        if PHONENUMBERS_AVAILABLE:
            try:
                parsed_phone = phonenumbers.parse(normalized_phone, country_hint)
                details["parsed_successfully"] = True
                details["is_possible"] = phonenumbers.is_possible_number(parsed_phone)
                details["is_valid_number"] = phonenumbers.is_valid_number(parsed_phone)
                
                if parsed_phone.country_code:
                    details["country_code"] = parsed_phone.country_code
                if parsed_phone.national_number:
                    details["national_number"] = str(parsed_phone.national_number)
                
                if details["is_valid_number"]:
                    details["international_format"] = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                    details["national_format"] = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.NATIONAL)
                    
                    # Correção: usar phonenumbers.number_type
                    num_type = phonenumbers.number_type(parsed_phone)
                    details["phone_type"] = self._get_phone_type_name_safe(num_type)

                    # Verificar tipo premium/toll-free/spam
                    if num_type in [PhoneNumberType.PREMIUM_RATE, PhoneNumberType.TOLL_FREE]:
                        message = f"Telefone válido, mas é de serviço tipo: {details['phone_type']}."
                        is_valid = True # Consideramos válido, mas com aviso
                        business_rule_code = PhoneRuleCodes.RN_TEL007
                        details["reason"].append("special_service_type")
                    elif num_type == PhoneNumberType.UNKNOWN:
                         message = f"Telefone válido, mas o tipo é desconhecido: {details['phone_type']}."
                         is_valid = True # Consideramos válido, mas com aviso
                         business_rule_code = PhoneRuleCodes.RN_TEL010
                         details["reason"].append("unknown_phone_type")
                    else:
                        is_valid = True
                        message = "Número de telefone válido (formato e checksum via phonenumbers)."
                        business_rule_code = PhoneRuleCodes.RN_TEL001
                else: # is_valid_number é False
                    if not details["is_possible"]:
                        message = "Número de telefone impossível (não é um número real)."
                        business_rule_code = PhoneRuleCodes.RN_TEL002
                        details["reason"].append("not_possible_number")
                    else:
                        message = "Número de telefone válido no formato, mas inválido em relação à existência/intervalo (via phonenumbers)."
                        business_rule_code = PhoneRuleCodes.RN_TEL002
                        details["reason"].append("invalid_number_range")

            except phonenumbers.NumberParseException as e:
                message = f"Formato de telefone inválido (erro de parsing: {e})."
                business_rule_code = PhoneRuleCodes.RN_TEL002
                details["reason"].append(f"parsing_error: {e.args[0].name}")
            except Exception as e:
                logger.error(f"Erro inesperado no phonenumbers para '{normalized_phone}': {e}", exc_info=True)
                message = f"Erro inesperado durante a validação do telefone: {e}. Revertendo para validação básica."
                is_valid = False # Considera inválido em caso de erro interno
                business_rule_code = PhoneRuleCodes.RN_TEL009
                details["reason"].append("unexpected_internal_error")
        else: # phonenumbers não disponível, fallback para regex
            # Regex básica para validação de telefone (muito simplificada)
            # Adapte esta regex para suas necessidades específicas de formato!
            if re.fullmatch(r'^\+?[0-9\s\-\(\)]{8,20}$', normalized_phone):
                is_valid = True
                message = "Número de telefone válido (formato básico via regex). Validação avançada desativada."
                business_rule_code = PhoneRuleCodes.RN_TEL001
                details["reason"].append("regex_fallback_validation")
            else:
                is_valid = False
                message = "Formato de telefone inválido (regex básica)."
                business_rule_code = PhoneRuleCodes.RN_TEL002
                details["reason"].append("regex_format_mismatch")

        # Se o telefone não passou na validação de formato/parsing, retorna imediatamente
        if not is_valid:
            return self._format_result(
                is_valid=False,
                dado_original=phone_number_str, # Passa dado_original
                dado_normalizado=normalized_phone,
                mensagem=message,
                details=details,
                business_rule_applied={"code": business_rule_code, "type": "Telefone - Validação Primária", "name": message}
            )

        # 2. Simular consulta em base de dados cadastral (se o número for válido até aqui)
        # Usar o formato internacional como chave para a base de dados simulada, se disponível
        db_lookup_key = details.get("international_format") or normalized_phone
        customer_data = self.simulated_customer_database.get(db_lookup_key)

        if customer_data:
            details["simulated_db_status"] = "Found"
            details["is_active_in_database"] = customer_data.get("is_active", False)
            details["is_fraud_risk"] = customer_data.get("is_fraud_risk", False)
            details["customer_name"] = customer_data.get("customer_name")

            if details["is_fraud_risk"]:
                message = f"Telefone válido, mas possui sinalização de risco/fraude na base cadastral."
                is_valid = False # Considerar inválido se for risco de fraude
                business_rule_code = PhoneRuleCodes.RN_TEL005
                details["reason"].append("fraud_risk_detected")
            elif not details["is_active_in_database"]:
                message = f"Telefone válido, mas está inativo na base cadastral."
                is_valid = False # Considerar inválido se inativo
                business_rule_code = PhoneRuleCodes.RN_TEL005
                details["reason"].append("inactive_in_database")
            else:
                message = f"Telefone válido e ativo na base cadastral."
                is_valid = True
                business_rule_code = PhoneRuleCodes.RN_TEL001 # Ainda é válido e ativo
        else:
            details["simulated_db_status"] = "Not Found"
            message = f"Telefone válido (formato), mas não encontrado na base cadastral simulada."
            is_valid = False # Não encontrado na base, pode ser considerado inválido para o negócio
            business_rule_code = PhoneRuleCodes.RN_TEL004
            details["reason"].append("not_found_in_simulated_db")
            
        # Retorna o resultado final
        return self._format_result(
            is_valid=is_valid,
            dado_original=phone_number_str, # Passa dado_original
            dado_normalizado=details.get("international_format") or normalized_phone, # Normalizado para o formato internacional, se possível
            mensagem=message,
            details=details,
            business_rule_applied={"code": business_rule_code, "type": "Telefone - Validação Final", "name": message}
        )

    def _get_phone_type_name_safe(self, num_type: 'phonenumbers.PhoneNumberType') -> str:
        """
        Retorna o nome do tipo de telefone de forma segura,
        mapeando o enum para string.
        """
        return self._phone_type_names.get(num_type, "UNKNOWN_TYPE_ERROR")
