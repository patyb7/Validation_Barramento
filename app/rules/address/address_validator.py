import logging
import re
from typing import Dict, Any, Optional
from app.rules.base import BaseValidator
from app.rules.address.cep.validator import CEPValidator # Importar o CEPValidator

logger = logging.getLogger(__name__)

class AddressRuleCodes:
    RN_ADDR001 = "RN_ADDR001"  # Endereço válido e completo
    RN_ADDR002 = "RN_ADDR002"  # Endereço com campos obrigatórios ausentes
    RN_ADDR003 = "RN_ADDR003"  # CEP inválido (formato ou não encontrado) - tratado por CEPValidator
    RN_ADDR004 = "RN_ADDR004"  # Endereço não correspondente ao CEP (simulado)
    RN_ADDR005 = "RN_ADDR005"  # Endereço válido, mas com inconsistências leves (ex: número não numérico)
    RN_ADDR006 = "RN_ADDR006"  # Endereço não encontrado na base externa (simulado)
    RN_ADDR007 = "RN_ADDR007"  # Input vazio ou tipo inválido (não dicionário ou vazio)

class AddressValidator(BaseValidator):
    """
    Validador composto para dados de endereço.
    Valida a presença de campos obrigatórios e, opcionalmente, a consistência
    com um CEP validado (se fornecido).
    """
    def __init__(self, cep_validator: CEPValidator): # Adicionado cep_validator
        super().__init__(origin_name="address_validator")
        self.cep_validator = cep_validator # Armazenar a instância do CEPValidator
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
        original_address_data = data # Captura o dado original
        logger.info(f"Iniciando validação de endereço: {original_address_data}...")

        # 1. Verificação de Input Vazio ou Inválido
        if not isinstance(original_address_data, dict) or not original_address_data:
            return self._format_result(
                is_valid=False,
                dado_original=original_address_data,
                dado_normalizado=None,
                mensagem="Endereço vazio ou tipo inválido. Esperado um dicionário não vazio.",
                details={"input_original": original_address_data},
                business_rule_applied={"code": AddressRuleCodes.RN_ADDR007, "type": "Endereço - Validação Primária", "name": "Input de Endereço Vazio ou Inválido"}
            )

        # Campos esperados e obrigatórios
        required_fields = ["logradouro", "numero", "bairro", "cidade", "estado", "cep"]
        missing_fields = [f for f in required_fields if not original_address_data.get(f) or not str(original_address_data.get(f)).strip()]

        is_valid = True
        message = "Endereço válido."
        business_rule_code = AddressRuleCodes.RN_ADDR001
        
        details = {
            "input_original": original_address_data,
            "missing_fields": missing_fields,
            "normalized_address": {},
            "inconsistencies": [],
            "simulated_consistency": True, # Para simular a consistência com o CEP
            "reason": []
        }

        if missing_fields:
            is_valid = False
            message = f"Campos obrigatórios ausentes: {', '.join(missing_fields)}."
            business_rule_code = AddressRuleCodes.RN_ADDR002
            details["reason"].append("missing_required_fields")
            
            # Se faltam campos obrigatórios, retorna imediatamente
            return self._format_result(
                is_valid=False,
                dado_original=original_address_data,
                dado_normalizado=None,
                mensagem=message,
                details=details,
                business_rule_applied={"code": business_rule_code, "type": "Endereço - Validação Primária", "name": "Campos Obrigatórios Ausentes"}
            )

        # Normaliza e valida campos individuais (ex: limpeza, tipo)
        normalized_address = {}
        for field in required_fields:
            value = str(original_address_data[field]).strip()
            normalized_address[field] = value
            # Exemplo de validação de campo individual (não exaustivo)
            if field == "numero" and not value.replace('-', '').isalnum(): # Aceita números e hífens
                details["inconsistencies"].append(f"Número de endereço contém caracteres inválidos: {value}")
                details["reason"].append("invalid_address_number_chars")
                is_valid = False # Considera uma inconsistência leve, mas pode ser fatal dependendo da regra
                business_rule_code = AddressRuleCodes.RN_ADDR005
            
        details["normalized_address"] = normalized_address

        if not is_valid: # Se houve inconsistências nos campos normalizados
             return self._format_result(
                is_valid=False,
                dado_original=original_address_data,
                dado_normalizado=normalized_address,
                mensagem="Endereço válido, mas com inconsistências leves em campos.",
                details=details,
                business_rule_applied={"code": business_rule_code, "type": "Endereço - Validação Leve", "name": "Inconsistências em Campos de Endereço"}
            )

        # Validação do CEP usando o CEPValidator injetado
        cep_validation_result = await self.cep_validator.validate(normalized_address["cep"])
        details["cep_validation_result"] = cep_validation_result

        if not cep_validation_result["is_valid"]:
            # Se o CEP for inválido pelo CEPValidator, o endereço completo também é inválido
            message = f"Endereço inválido: {cep_validation_result['mensagem']}"
            business_rule_code = cep_validation_result["business_rule_applied"]["code"] # Usa o código do CEPValidator
            details["reason"].append("cep_invalidated_by_sub_validator")
            is_valid = False
            
            return self._format_result(
                is_valid=is_valid,
                dado_original=original_address_data,
                dado_normalizado=normalized_address,
                mensagem=message,
                details=details,
                business_rule_applied={"code": business_rule_code, "type": "Endereço - Validação de Dependência", "name": message}
            )

        # Simular validação de consistência do endereço com o CEP
        # Em um cenário real, isso envolveria uma consulta a um serviço de geocodificação ou API de CEP avançada
        # que retornaria o logradouro, bairro, cidade, estado para o CEP fornecido
        # e compararia com os dados recebidos.

        # CEP fictício que "não corresponde" ou "não é encontrado na base externa"
        if normalized_address["cep"] == "07273-120" or normalized_address["cep"] == "12345-000":
            details["simulated_consistency"] = False
            message = "Endereço: CEP válido, mas não encontrado na base externa. Validação prossegue, mas pode ser incompleta."
            business_rule_code = AddressRuleCodes.RN_ADDR006
            details["reason"].append("cep_not_found_in_external_db")
            is_valid = True # Considera válido, mas com aviso (WARNING)
            logger.warning(f"AddressValidation: {message} para CEP {normalized_address['cep']}")
        elif normalized_address["cep"] == "99999-999":
            details["simulated_consistency"] = False
            message = "Endereço: CEP válido, mas não correspondente aos demais campos do endereço (simulado)."
            business_rule_code = AddressRuleCodes.RN_ADDR004
            details["reason"].append("address_cep_inconsistency")
            is_valid = False # Inconsistência grave
        
        # Conclusão da validação
        final_is_valid = is_valid and (not details["inconsistencies"]) and details["simulated_consistency"]
        
        if not final_is_valid:
            if not details["simulated_consistency"]: # Se a inconsistência grave for o CEP
                 final_message = message # A mensagem já foi definida acima
                 final_business_rule = {"code": business_rule_code, "type": "Endereço - Validação de Consistência", "name": final_message}
            elif details["inconsistencies"]: # Se for por inconsistências leves já tratadas
                 final_message = "Endereço válido, mas com inconsistências leves em campos."
                 final_business_rule = {"code": AddressRuleCodes.RN_ADDR005, "type": "Endereço - Validação Leve", "name": final_message}
            else:
                 final_message = "Endereço inválido por razão desconhecida." # Fallback
                 final_business_rule = {"code": self.VAL_GENERIC_INVALID, "type": "Endereço - Validação Final", "name": final_message}
        else:
            final_message = "Endereço válido e consistente."
            final_business_rule = {"code": AddressRuleCodes.RN_ADDR001, "type": "Endereço - Validação Final", "name": final_message}


        return self._format_result(
            is_valid=final_is_valid,
            dado_original=original_address_data,
            dado_normalizado=normalized_address,
            mensagem=final_message,
            details=details,
            business_rule_applied=final_business_rule
        )
