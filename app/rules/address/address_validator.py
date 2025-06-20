# app/rules/address/address_validator.py

import logging
from typing import Dict, Any, Optional

from app.rules.base import BaseValidator # Importa a classe BaseValidator
from app.rules.address.cep.validator import CEPValidator # Importa o CEPValidator

logger = logging.getLogger(__name__)

# Códigos de Regra específicos para validação de Endereço (Mantidos para clareza, mas as de CEP vêm do CEPValidator)
VAL_END001 = "VAL_END001" # Endereço válido e completo
VAL_END002 = "VAL_END002" # Endereço inválido (erros estruturais, campos obrigatórios)
VAL_END003 = "VAL_END003" # Input vazio ou tipo inválido
VAL_END004 = "VAL_END004" # CEP não informado ou inválido para consulta
VAL_END005 = "VAL_END005" # Erro na normalização/formatação

class AddressValidator(BaseValidator):
    """
    Validador de endereços com suporte a validação de CEP e normalização.
    Utiliza o CEPValidator para a parte específica do CEP.
    """

    def __init__(self, cep_validator: CEPValidator):
        super().__init__(origin_name="address_validator")
        self.cep_validator = cep_validator
        logger.info("AddressValidator inicializado.")

    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Valida um dicionário de dados de endereço, implementando o método abstrato 'validate'.

        Args:
            data (Any): Os dados do endereço a serem validados. Esperado um dicionário,
                        ex: {'logradouro': '...', 'numero': '...', 'cep': '...'}.
            **kwargs: Parâmetros adicionais que podem ser passados (mantido para compatibilidade).

        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação, contendo:
                            - "is_valid" (bool): Se o endereço é considerado válido.
                            - "dado_normalizado" (str): O endereço normalizado em uma string formatada.
                            - "mensagem" (str): Mensagem explicativa do resultado.
                            - "origem_validacao" (str): Fonte da validação.
                            - "details" (dict): Detalhes adicionais (validação de CEP, etc.).
                            - "business_rule_applied" (dict): Detalhes da regra de negócio aplicada.
        """
        # Garante que 'data' é um dicionário para o restante da lógica
        if not isinstance(data, dict):
            return self._format_result(
                is_valid=False,
                dado_normalizado=None,
                mensagem="Dados de endereço esperados como dicionário, mas recebido tipo inválido.",
                details={"input_original": data},
                business_rule_applied={"code": VAL_END003, "type": "endereco"}
            )

        address_data = data.copy() # Use a cópia para evitar modificar o input original
        original_address_data = address_data.copy()
        
        # Prepara o dicionário de detalhes
        details = {
            "input_original": original_address_data,
            "cep_validation": {},
            "normalization_status": "not_attempted",
            "required_fields_check": {}
        }
        
        is_valid = False
        message = "Endereço inválido: falha na validação estrutural."
        normalized_address = None
        validation_code = VAL_END002

        # 1. Verificação de Input Vazio (para o dicionário)
        if not address_data:
            message = "Dados de endereço vazios. Esperado um dicionário não vazio."
            validation_code = VAL_END003
            return self._format_result(False, None, message, details, {"code": validation_code})

        # 2. Validação do CEP usando CEPValidator
        cep_input = address_data.get("cep")
        if cep_input:
            cep_validation_result = await self.cep_validator.validate(cep_input)
            details["cep_validation"] = cep_validation_result # Adiciona todos os detalhes do CEP
            
            if not cep_validation_result.get("is_valid"):
                message = f"Endereço inválido: CEP inválido ou com erro. {cep_validation_result.get('message', '')}"
                # Acessa a constante VAL_CEP004 da instância do cep_validator
                validation_code = cep_validation_result.get("business_rule_applied", {}).get("code", self.cep_validator.VAL_CEP004)
                return self._format_result(False, None, message, details, {"code": validation_code})
            
            # Acessa a constante VAL_CEP002 da instância do cep_validator
            if cep_validation_result.get("business_rule_applied", {}).get("code") == self.cep_validator.VAL_CEP002:
                message = "Endereço: CEP válido, mas não encontrado na base externa. Validação prossegue, mas pode ser incompleta."
                logger.warning(f"AddressValidation: {message} para CEP {cep_input}")
            else:
                if cep_validation_result.get("details", {}).get("external_api_data"):
                    address_data.update(cep_validation_result["details"]["external_api_data"])
                    details["normalization_status"] = "enriched_by_cep_api"
                    logger.debug(f"Endereço enriquecido com dados do CEP API: {address_data}")
        else:
            message = "Endereço inválido: CEP não informado. Não é possível validar ou enriquecer sem o CEP."
            validation_code = VAL_END004
            return self._format_result(False, None, message, details, {"code": validation_code})


        # 3. Verificação de Campos Obrigatórios (após possível enriquecimento pelo CEP)
        required_fields_for_full_address = [
            "logradouro", "numero", "bairro", "localidade", "uf", "cep"
        ]
        missing_fields = [field for field in required_fields_for_full_address if not address_data.get(field)]
        
        if missing_fields:
            message = f"Endereço inválido: Campos obrigatórios ausentes: {', '.join(missing_fields)}."
            details["required_fields_check"] = {"status": "missing", "missing_fields": missing_fields}
            validation_code = VAL_END002 # Erro estrutural
            return self._format_result(False, None, message, details, {"code": validation_code})
        else:
            details["required_fields_check"] = {"status": "ok"}


        # 4. Normalização e Formatação do Endereço Completo
        try:
            uf = address_data.get("uf", "").upper()
            if len(uf) != 2:
                message = "Endereço inválido: UF (Estado) com formato inválido."
                validation_code = VAL_END002
                return self._format_result(False, None, message, details, {"code": validation_code})

            # Usa o método _clean_cep do cep_validator para garantir consistência
            normalized_cep_for_format = self.cep_validator._clean_cep(address_data.get('cep', ''))

            normalized_address = (
                f"{address_data.get('logradouro', '')}, {address_data.get('numero', '')}"
                f"{' - ' + address_data.get('complemento') if address_data.get('complemento') else ''}"
                f" - {address_data.get('bairro', '')}"
                f", {address_data.get('localidade', '')}-{uf}"
                f", CEP {normalized_cep_for_format}"
            ).strip()
            details["normalization_status"] = "formatted_to_canonical"
            
            is_valid = True
            message = "Endereço válido e normalizado."
            validation_code = VAL_END001

        except Exception as e:
            is_valid = False
            message = f"Erro na normalização/formatação do endereço: {e}."
            validation_code = VAL_END005
            logger.error(f"Erro na normalização do endereço {original_address_data}: {e}", exc_info=True)

        return self._format_result(
            is_valid,
            normalized_address,
            message,
            details,
            {"code": validation_code, "type": "endereco"}
        )
# Exemplo de uso:
# cep_validator = CEPValidator()
# address_validator = AddressValidator(cep_validator)
# result = await address_validator.validate({
#     "logradouro": "Praça da Sé",
#     "numero": "1",
#     "bairro": "Sé",
#     "localidade": "São Paulo",
#     "uf": "SP",
#     "cep": "01001000"
# })
# print(result)