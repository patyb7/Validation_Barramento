import logging
import re
from typing import Dict, Any, Optional

from app.rules.base import BaseValidator
from app.rules.address.cep.validator import CEPValidator
from app.tests.simulated_data import SIMULATED_CEP_RESPONSES, SIMULATED_ADDRESS_CONSISTENCY_MAP

logger = logging.getLogger(__name__)

class AddressRuleCodes:
    RN_ADDR001 = "RN_ADDR001"    # Endereço válido e completo
    RN_ADDR002 = "RN_ADDR002"    # Endereço com campos obrigatórios ausentes
    RN_ADDR003 = "RN_ADDR003"    # CEP inválido (formato ou não encontrado) - tratado por CEPValidator
    RN_ADDR004 = "RN_ADDR004"    # Endereço não correspondente ao CEP (inconsistência de dados)
    RN_ADDR005 = "RN_ADDR005"    # Endereço válido, mas com inconsistências leves (ex: número não numérico)
    RN_ADDR006 = "RN_ADDR006"    # CEP válido, mas não encontrado na base externa (API de CEP simulada não achou)
    RN_ADDR007 = "RN_ADDR007"    # Input vazio ou tipo inválido (não dicionário ou vazio)
    RN_ADDR008 = "RN_ADDR008"    # Erro na consulta de API de CEP (tratado por CEPValidator, mas importante aqui)

class AddressValidator(BaseValidator):
    """
    Validador composto para dados de endereço.
    Valida a presença de campos obrigatórios e a consistência
    com um CEP validado (se fornecido).
    """
    def __init__(self, cep_validator: CEPValidator):
        super().__init__(origin_name="address_validator")
        self.cep_validator = cep_validator
        logger.info("AddressValidator inicializado.")

    async def validate(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Valida um dicionário contendo dados de endereço.

        Args:
            data (Dict[str, Any]): O dicionário de dados do endereço (logradouro, numero, bairro, cidade, estado, cep).
            **kwargs: Parâmetros adicionais (compatibilidade com BaseValidator).

        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação padronizado.
        """
        original_address_data = data.copy() # Use a copy to avoid modifying the original input reference
        logger.info(f"Iniciando validação de endereço: {original_address_data}...")

        result_details = {
            "input_original": original_address_data,
            "missing_fields": [],
            "normalized_address": {},
            "inconsistencies": [],
            "consistency_with_cep_api": True, # Assume True, pode ser False se houver divergência ou CEP não encontrado pela API
            "reason": []
        }

        # 1. Verificação de Input Vazio ou Inválido
        if not isinstance(original_address_data, dict) or not original_address_data:
            return self._format_result(
                is_valid=False,
                dado_original=original_address_data,
                dado_normalizado=None,
                mensagem="Endereço vazio ou tipo inválido. Esperado um dicionário não vazio.",
                details=result_details,
                business_rule_applied={"code": AddressRuleCodes.RN_ADDR007, "type": "Endereço - Validação Primária", "name": "Input de Endereço Vazio ou Inválido"}
            )

        # Normalize provided fields first for consistency
        for field, value in original_address_data.items():
            if isinstance(value, str):
                result_details["normalized_address"][field] = value.strip()
            else:
                result_details["normalized_address"][field] = value

        # 2. Validação e Enriquecimento do CEP usando o CEPValidator injetado
        cep_raw = result_details["normalized_address"].get("cep")
        cep_validation_result = await self.cep_validator.validate(cep_raw)
        result_details["cep_validation_result"] = cep_validation_result

        if not cep_validation_result["is_valid"]:
            # If CEP is invalid by CEPValidator, the full address is also invalid
            message = f"Endereço inválido: {cep_validation_result['mensagem']}"
            business_rule_code = cep_validation_result["business_rule_applied"]["code"]
            result_details["reason"].append("cep_invalidated_by_sub_validator")
            return self._format_result(
                is_valid=False,
                dado_original=original_address_data,
                dado_normalizado=result_details["normalized_address"],
                mensagem=message,
                details=result_details,
                business_rule_applied={"code": business_rule_code, "type": "Endereço - Validação de Dependência", "name": message}
            )

        # If CEP is valid but not found in the external API (VAL_CEP002) or API error (VAL_CEP006)
        if cep_validation_result["business_rule_applied"]["code"] == self.cep_validator.VAL_CEP002:
            result_details["consistency_with_cep_api"] = False
            # We don't mark as invalid here, but note the lack of full consistency check below
            logger.warning(f"AddressValidation: CEP válido, mas não encontrado na base externa (ViaCEP simulado). A consistência não pôde ser verificada.")
            result_details["reason"].append("cep_valid_but_not_found_in_api")
        elif cep_validation_result["business_rule_applied"]["code"] == self.cep_validator.VAL_CEP006:
            result_details["consistency_with_cep_api"] = False
            message = f"Endereço inválido: Erro ao consultar API externa de CEP: {cep_validation_result['mensagem']}. Validação comprometida."
            business_rule_code = AddressRuleCodes.RN_ADDR008
            result_details["reason"].append("cep_api_error")
            return self._format_result(
                is_valid=False,
                dado_original=original_address_data,
                dado_normalizado=result_details["normalized_address"],
                mensagem=message,
                details=result_details,
                business_rule_applied={"code": business_rule_code, "type": "Endereço - Validação de Dependência", "name": "Erro na Consulta da API de CEP"}
            )
        
        # 3. Enrich address data from CEP API result IF CEP was found (VAL_CEP001)
        if cep_validation_result["business_rule_applied"]["code"] == self.cep_validator.VAL_CEP001:
            api_address_data = cep_validation_result["details"].get("external_api_data", {})
            
            # Map API fields to your address fields
            api_to_address_map = {
                "logradouro": "logradouro",
                "bairro": "bairro",
                "localidade": "cidade",
                "uf": "estado"
            }

            for api_field, address_field in api_to_address_map.items():
                if address_field not in result_details["normalized_address"] or not result_details["normalized_address"][address_field]:
                    # Fill missing address fields from API data if they are missing
                    if api_address_data.get(api_field):
                        result_details["normalized_address"][address_field] = api_address_data[api_field]
                        logger.debug(f"Preenchido campo '{address_field}' com dado da API de CEP: {api_address_data[api_field]}")

        # 4. Re-check for Missing Required Fields AFTER CEP enrichment attempt
        # This is CRUCIAL: only check for missing fields after attempting to fill them from CEP
        required_fields = ["logradouro", "numero", "bairro", "cidade", "estado", "cep"]
        for field in required_fields:
            if not result_details["normalized_address"].get(field) or not str(result_details["normalized_address"].get(field)).strip():
                result_details["missing_fields"].append(field)

        if result_details["missing_fields"]:
            message = f"Campos obrigatórios ausentes: {', '.join(result_details['missing_fields'])}."
            result_details["reason"].append("missing_required_fields")
            return self._format_result(
                is_valid=False,
                dado_original=original_address_data,
                dado_normalizado=result_details["normalized_address"],
                mensagem=message,
                details=result_details,
                business_rule_applied={"code": AddressRuleCodes.RN_ADDR002, "type": "Endereço - Validação Primária", "name": "Campos Obrigatórios Ausentes"}
            )

        # Normalize and validate individual fields (e.g., cleaning, type)
        # This loop now operates on potentially enriched `normalized_address`
        for field in required_fields: # Re-iterate to ensure all fields are properly handled, especially "numero"
            value = str(result_details["normalized_address"][field]).strip()
            # Specific validation for the 'numero' field
            if field == "numero" and not re.fullmatch(r'^[a-zA-Z0-9\s\-\.]+$', value):
                result_details["inconsistencies"].append(f"Número de endereço contém caracteres inválidos: '{value}'.")
                result_details["reason"].append("invalid_address_number_chars")
                logger.warning(f"AddressValidation: Número de endereço com caracteres inválidos: '{value}'")
        
        # 5. Validação de Consistência com o CEP (usando SIMULATED_ADDRESS_CONSISTENCY_MAP)
        # This validation only makes sense if the CEP was found in the simulated API (VAL_CEP001)
        if cep_validation_result["business_rule_applied"]["code"] == self.cep_validator.VAL_CEP001:
            # We already have api_address_data from previous step
            api_address_data = cep_validation_result["details"].get("external_api_data", {})

            if api_address_data: # Make sure API data was actually returned and not empty
                # Compare logradouro, bairro, cidade, uf (estado)
                input_to_api_field = {
                    "logradouro": "logradouro",
                    "bairro": "bairro",
                    "cidade": "localidade",
                    "estado": "uf"
                }

                for input_field, api_field in input_to_api_field.items():
                    provided_value = result_details["normalized_address"].get(input_field, "").lower()
                    expected_value = api_address_data.get(api_field, "").lower()
                    
                    if provided_value and expected_value and provided_value != expected_value:
                        result_details["inconsistencies"].append(
                            f"Campo '{input_field}' ('{provided_value}') diverge do esperado para o CEP ('{expected_value}')."
                        )
                        result_details["reason"].append(f"inconsistency_{input_field}")
                        result_details["consistency_with_cep_api"] = False
            else:
                # The CEP was valid by ViaCEP, but we have no consistency data in our simulated map (or ViaCEP returned empty address)
                logger.warning(f"AddressValidation: CEP {cep_validation_result['dado_normalizado']} encontrado na ViaCEP, mas não há dados de endereço para consistência.")
                result_details["reason"].append("cep_found_but_no_consistency_data")

        # 6. Determinação do Resultado Final
        is_final_valid = True
        final_message = "Endereço válido e consistente."
        final_business_rule = {"code": AddressRuleCodes.RN_ADDR001, "type": "Endereço - Validação Final", "name": "Endereço Válido"}

        if result_details["inconsistencies"]:
            is_final_valid = False
            # Prioritize the most severe inconsistency or the first found
            if "address_cep_inconsistency" in result_details["reason"] or not result_details["consistency_with_cep_api"]:
                final_message = "Endereço válido, mas com inconsistências entre os dados e o CEP."
                final_business_rule = {"code": AddressRuleCodes.RN_ADDR004, "type": "Endereço - Validação de Consistência", "name": "Inconsistência de Endereço com CEP"}
            elif "invalid_address_number_chars" in result_details["reason"]:
                final_message = "Endereço válido, mas com inconsistências leves em campos (ex: número)."
                final_business_rule = {"code": AddressRuleCodes.RN_ADDR005, "type": "Endereço - Validação Leve", "name": "Inconsistências em Campos de Endereço"}
            else:
                final_message = "Endereço válido, mas com inconsistências detectadas."
                final_business_rule = {"code": AddressRuleCodes.RN_ADDR005, "type": "Endereço - Validação Leve", "name": "Inconsistências Diversas"}


        # If the CEP was valid but not found in the external base (RN_ADDR006), the address is considered "valid with warning"
        # This applies only if no other 'is_valid=False' condition was met
        if cep_validation_result["business_rule_applied"]["code"] == self.cep_validator.VAL_CEP002 and is_final_valid:
            final_message = "Endereço válido, mas o CEP não foi encontrado na base externa. A consistência total não pôde ser confirmada."
            final_business_rule = {"code": AddressRuleCodes.RN_ADDR006, "type": "Endereço - Validação com Aviso", "name": "CEP não Encontrado na Base Externa"}
            # We keep is_final_valid as True, as the address is not *invalid*, but has a risk/warning.
            # You can adjust this logic to make is_final_valid=False if this condition is critical for you.


        logger.debug(f"Validação de Endereço para '{original_address_data}': {final_message}")
        
        return self._format_result(
            is_valid=is_final_valid,
            dado_original=original_address_data,
            dado_normalizado=result_details["normalized_address"],
            mensagem=final_message,
            details=result_details,
            business_rule_applied=final_business_rule
        )

    def _format_result(self, is_valid: bool, dado_original: Any, dado_normalizado: Optional[Dict[str, Any]], mensagem: str,
                       details: Dict[str, Any], business_rule_applied: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata o resultado da validação em um dicionário padronizado.
        """
        return {
            "is_valid": is_valid,
            "dado_original": dado_original,
            "dado_normalizado": dado_normalizado,
            "mensagem": mensagem,
            "origem_validacao": self.origin_name,
            "details": details,
            "business_rule_applied": business_rule_applied
        }