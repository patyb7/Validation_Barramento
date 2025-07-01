# app/rules/address/cep/vaildator.py

import re
import logging
import asyncio
from typing import Dict, Any, Optional

from app.rules.base import BaseValidator
# Importa a base de dados simulada e o CEP de falha de API
from app.tests.simulated_data import SIMULATED_CEP_RESPONSES, SIMULATED_CEP_API_FAILURE_CEP

logger = logging.getLogger(__name__)

class CEPValidator(BaseValidator):
    """
    Validador de Códigos de Endereçamento Postal (CEP) para o Brasil.
    Realiza validação de formato, verifica padrões comuns inválidos (sequenciais/repetidos)
    e simula consulta a uma API externa (como ViaCEP) para validação e enriquecimento.
    """
    # Códigos de Regra específicos para validação de CEP
    VAL_CEP001 = "VAL_CEP001" # CEP válido e encontrado (ex: ViaCEP)
    VAL_CEP002 = "VAL_CEP002" # CEP válido, mas não encontrado na API externa
    VAL_CEP003 = "VAL_CEP003" # Input vazio ou tipo inválido
    VAL_CEP004 = "VAL_CEP004" # CEP sequencial ou com dígitos repetidos (ex: 11111-111, 12345-678)
    VAL_CEP005 = "VAL_CEP005" # Formato básico inválido (não numérico, comprimento errado)
    VAL_CEP006 = "VAL_CEP006" # Erro na consulta da API externa (timeout, serviço fora)

    def __init__(self):
        super().__init__(origin_name="cep_validator")
        logger.info("CEPValidator inicializado.")

    def _clean_cep(self, cep: str) -> str:
        """Remove caracteres não numéricos do CEP."""
        if not cep:
            return ""
        return re.sub(r'\D', '', str(cep))

    def _is_sequential_or_repeated(self, cleaned_cep: str) -> bool:
        """Verifica se o CEP tem 4 ou mais dígitos sequenciais ou repetidos."""
        if len(cleaned_cep) < 4:
            return False

        # Verifica sequenciais (ex: 1234, 5432)
        for i in range(len(cleaned_cep) - 3):
            subset = cleaned_cep[i:i+4]
            if all(d.isdigit() for d in subset):
                s0, s1, s2, s3 = int(subset[0]), int(subset[1]), int(subset[2]), int(subset[3])
                # Verifica sequências crescentes ou decrescentes
                if (s0 + 1 == s1 and s1 + 1 == s2 and s2 + 1 == s3) or \
                   (s0 - 1 == s1 and s1 - 1 == s2 and s2 - 1 == s3):
                    return True

        # Verifica repetidos (ex: 1111, 8888)
        for i in range(len(cleaned_cep) - 3):
            subset = cleaned_cep[i:i+4]
            if subset[0] == subset[1] == subset[2] == subset[3]:
                return True
        return False

    async def _consult_via_cep_api(self, cep: str) -> Optional[Dict[str, Any]]:
        """
        Simula a consulta à API ViaCEP usando dados de teste centralizados de `simulated_data.py`.
        """
        logger.debug(f"Simulando consulta à API ViaCEP para CEP: {cep}")
        await asyncio.sleep(0.05) # Simula um pequeno atraso de rede

        # Simula erro de API (ex: timeout, serviço fora) para o CEP definido em simulated_data.py
        if cep == SIMULATED_CEP_API_FAILURE_CEP:
            logger.error(f"Simulando falha de API para o CEP: {cep}")
            raise Exception("Simulated API connection error or timeout.")

        # Obtém os dados da resposta simulada do dicionário SIMULATED_CEP_RESPONSES
        response_data = SIMULATED_CEP_RESPONSES.get(cep)
        
        return response_data

    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Valida um CEP (Código de Endereçamento Postal).

        Args:
            data (Any): O número do CEP a ser validado (pode conter formatação).
            **kwargs: Parâmetros adicionais (compatibilidade com BaseValidator).

        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação, contendo:
                            - "is_valid" (bool): Se o CEP é considerado válido.
                            - "dado_original" (Any): O dado original que foi submetido.
                            - "dado_normalizado" (str): O CEP limpo (apenas dígitos).
                            - "mensagem" (str): Mensagem explicativa do resultado.
                            - "origem_validacao" (str): Fonte da validação.
                            - "details" (dict): Detalhes adicionais (dados da API externa, etc.).
                            - "business_rule_applied" (dict): Detalhes da regra de negócio aplicada.
        """
        original_cep = data
        
        # 1. Verificação de Input Vazio ou Inválido
        if not isinstance(original_cep, str) or not original_cep.strip():
            return self._format_result(
                is_valid=False,
                dado_original=original_cep,
                dado_normalizado=None,
                mensagem="CEP vazio ou tipo inválido.",
                details={"input_original": original_cep},
                business_rule_applied={"code": self.VAL_CEP003, "type": "CEP - Validação Primária", "name": "Input de CEP Inválido"}
            )

        cleaned_cep = self._clean_cep(original_cep)

        result_details = {"input_original": original_cep, "cleaned_data": cleaned_cep}

        # 2. Verificação de Formato Básico e Comprimento
        if not cleaned_cep.isdigit() or len(cleaned_cep) != 8:
            return self._format_result(
                is_valid=False,
                dado_original=original_cep,
                dado_normalizado=cleaned_cep,
                mensagem="Formato de CEP inválido: deve conter exatamente 8 dígitos numéricos.",
                details=result_details,
                business_rule_applied={"code": self.VAL_CEP005, "type": "CEP - Validação Primária", "name": "Formato Básico de CEP Inválido"}
            )

        # 3. Verificação de Padrões Sequenciais/Repetidos
        if self._is_sequential_or_repeated(cleaned_cep):
            return self._format_result(
                is_valid=False,
                dado_original=original_cep,
                dado_normalizado=cleaned_cep,
                mensagem="CEP inválido: contém dígitos sequenciais ou repetidos (e.g., 11111-111, 12345-678).",
                details=result_details,
                business_rule_applied={"code": self.VAL_CEP004, "type": "CEP - Validação Primária", "name": "CEP com Padrão Sequencial/Repetido"}
            )

        # 4. Consulta à API Externa (simulada)
        api_data = None
        try:
            api_data = await self._consult_via_cep_api(cleaned_cep)
            result_details["external_api_response_raw"] = api_data
            if api_data and not api_data.get("erro"):
                is_valid_cep = True
                message = "CEP válido e encontrado na base externa (ViaCEP simulado)."
                validation_code = self.VAL_CEP001
                result_details["address_found"] = True
                result_details["external_api_data"] = api_data
            else:
                is_valid_cep = True # O formato é válido, mas não foi encontrado na simulação
                message = "CEP válido, mas não encontrado na base externa (ViaCEP simulado)."
                validation_code = self.VAL_CEP002
                result_details["address_found"] = False

        except Exception as e:
            is_valid_cep = False # Falha na API torna o resultado incerto ou inválido para processamento completo
            message = f"Erro ao consultar API externa de CEP: {e}. Validação base pode estar comprometida."
            validation_code = self.VAL_CEP006
            result_details["api_error"] = str(e)
            logger.error(f"Erro na validação de CEP {cleaned_cep} via API externa: {e}", exc_info=True)

        logger.debug(f"Validação de CEP para '{original_cep}' (limpo: '{cleaned_cep}'): {message}")
        
        return self._format_result(
            is_valid=is_valid_cep,
            dado_original=original_cep,
            dado_normalizado=cleaned_cep,
            mensagem=message,
            details=result_details,
            business_rule_applied={"code": validation_code, "type": "CEP - Validação Primária", "name": "Validação Final de CEP"}
        )

    def _format_result(self, is_valid: bool, dado_original: Any, dado_normalizado: Optional[str], mensagem: str,
                       details: Dict[str, Any], business_rule_applied: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata o resultado da validação em um dicionário padronizado.

        Args:
            is_valid (bool): Indica se a validação foi bem-sucedida.
            dado_original (Any): O dado original que foi submetido para validação.
            dado_normalizado (Optional[str]): O dado normalizado (ex: CEP limpo).
            mensagem (str): Mensagem de status da validação.
            details (Dict[str, Any]): Detalhes específicos da validação.
            business_rule_applied (Dict[str, Any]): Regra de negócio aplicada.

        Returns:
            Dict[str, Any]: Dicionário com o resultado da validação.
        """
        return {
            "is_valid": is_valid,
            "dado_original": dado_original,
            "dado_normalizado": dado_normalizado,
            "mensagem": mensagem,
            "origem_validacao": self.origin_name, # Garante que a origem seja sempre do validador
            "details": details,
            "business_rule_applied": business_rule_applied
        }