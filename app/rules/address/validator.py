# app/rules/address/address_validator.py
import logging
from typing import Dict, Any, Optional # Importe Optional
from app.rules.base import BaseValidator
from app.rules.address.cep.validator import CEPValidator

logger = logging.getLogger(__name__)

# Códigos de Regra específicos para validação de Endereço
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
    # --- MODIFICAÇÃO AQUI: Adicione db_manager ao __init__ para conformidade futura ---
    def __init__(self, cep_validator: CEPValidator, db_manager: Optional[Any] = None):
        super().__init__(origin_name="address_validator", db_manager=db_manager) # Passa db_manager para o BaseValidator
        self.cep_validator = cep_validator
        logger.info("AddressValidator inicializado.")

    # --- MODIFICAÇÃO CHAVE AQUI: Renomeie 'validate_address' para 'validate' ---
    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Valida um dicionário de dados de endereço. Este é o método principal
        de validação exigido pela BaseValidator.

        Args:
            data (Any): Um dicionário contendo os componentes do endereço,
                        ex: {'logradouro': '...', 'numero': '...', 'cep': '...'}.
                        Pode ser Any para flexibilidade, mas esperamos um Dict.
            **kwargs: Argumentos adicionais (atualmente não usados, mas para conformidade).

        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação, contendo:
                            - "is_valid" (bool): Se o endereço é considerado válido.
                            - "normalized_data" (str): O endereço normalizado em uma string formatada.
                            - "message" (str): Mensagem explicativa do resultado.
                            - "origin_validation" (str): Fonte da validação.
                            - "details" (dict): Detalhes adicionais (validação de CEP, etc.).
                            - "business_rule_applied" (dict): Detalhes da regra de negócio aplicada.
        """
        # Garanta que 'data' seja um dicionário. Se não for, trate como inválido.
        if not isinstance(data, dict):
            return self._format_result(
                is_valid=False,
                normalized_data=None, # Use normalized_data
                message="Dados de endereço vazios ou tipo inválido. Esperado um dicionário.",
                details={"input_original": data},
                business_rule_applied={"code": VAL_END003, "type": "endereco"}
            )

        address_data = data.copy() # Use address_data para a lógica interna
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

        # 2. Validação do CEP usando CEPValidator
        cep_input = address_data.get("cep")
        if cep_input:
            # Use await self.cep_validator.validate(cep_input)
            cep_validation_result = await self.cep_validator.validate(cep_input)
            details["cep_validation"] = cep_validation_result # Adiciona todos os detalhes do CEP
            
            if not cep_validation_result.get("is_valid"):
                message = f"Endereço inválido: CEP inválido ou com erro. {cep_validation_result.get('message', '')}"
                # Use o código de erro do CEP validator se disponível, caso contrário, VAL_END004
                validation_code = cep_validation_result.get("business_rule_applied", {}).get("code", VAL_END004)
                return self._format_result(False, None, message, details, {"code": validation_code, "type": "endereco"})
            
            # Se o CEP é válido mas não encontrado, isso pode ser um warning, não um blocker necessariamente
            # Adapte VAL_CEP002 para como você o define no seu CEPValidator
            # Se VAL_CEP002 for um atributo do CEPValidator
            if hasattr(self.cep_validator, 'VAL_CEP002') and \
               cep_validation_result.get("business_rule_applied", {}).get("code") == self.cep_validator.VAL_CEP002:
                message = "Endereço: CEP válido, mas não encontrado na base externa. Validação prossegue, mas pode ser incompleta."
                logger.warning(f"AddressValidation: {message} para CEP {cep_input}")
            else:
                # Se o CEP foi válido e encontrado, podemos usar os dados enriquecidos para normalização
                if cep_validation_result.get("details", {}).get("external_api_data"):
                    address_data.update(cep_validation_result["details"]["external_api_data"])
                    details["normalization_status"] = "enriched_by_cep_api"
                    logger.debug(f"Endereço enriquecido com dados do CEP API: {address_data}")
        else:
            message = "Endereço inválido: CEP não informado. Não é possível validar ou enriquecer sem o CEP."
            validation_code = VAL_END004
            return self._format_result(False, None, message, details, {"code": validation_code, "type": "endereco"})


        # 3. Verificação de Campos Obrigatórios (após possível enriquecimento pelo CEP)
        # Campos canônicos que esperamos ter após validação ou enriquecimento
        required_fields_for_full_address = [
            "logradouro", "numero", "bairro", "localidade", "uf", "cep"
        ]
        missing_fields = [field for field in required_fields_for_full_address if not address_data.get(field)]
        
        if missing_fields:
            message = f"Endereço inválido: Campos obrigatórios ausentes: {', '.join(missing_fields)}."
            details["required_fields_check"] = {"status": "missing", "missing_fields": missing_fields}
            validation_code = VAL_END002 # Erro estrutural
            return self._format_result(False, None, message, details, {"code": validation_code, "type": "endereco"})
        else:
            details["required_fields_check"] = {"status": "ok"}


        # 4. Normalização e Formatação do Endereço Completo
        try:
            # Garante que UF tem 2 caracteres
            uf = address_data.get("uf", "").upper()
            if len(uf) != 2:
                message = "Endereço inválido: UF (Estado) com formato inválido."
                validation_code = VAL_END002
                return self._format_result(False, None, message, details, {"code": validation_code, "type": "endereco"})

            # Construção de um endereço normalizado (exemplo de formato canônico)
            # Você pode ajustar este formato conforme a sua necessidade
            # Certifique-se de que self.cep_validator._clean_cep exista ou adapte.
            # Se _clean_cep não for público, pode precisar de um método público no CEPValidator para limpar o CEP.
            normalized_address = (
                f"{address_data.get('logradouro', '')}, {address_data.get('numero', '')}"
                f"{' - ' + address_data.get('complemento') if address_data.get('complemento') else ''}"
                f" - {address_data.get('bairro', '')}"
                f", {address_data.get('localidade', '')}-{uf}"
                f", CEP {self.cep_validator.normalize_cep(address_data.get('cep', '')) if hasattr(self.cep_validator, 'normalize_cep') else address_data.get('cep', '')}"
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