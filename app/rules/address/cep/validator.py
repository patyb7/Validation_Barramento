# app/rules/address/cep/validator.py

import re
import logging
import asyncio
from typing import Dict, Any, Optional
from app.rules.base import BaseValidator

# Códigos de Regra específicos para validação de CEP
VAL_CEP001 = "VAL_CEP001" # CEP válido e encontrado (ex: ViaCEP)
VAL_CEP002 = "VAL_CEP002" # CEP válido, mas não encontrado na API externa
VAL_CEP003 = "VAL_CEP003" # Input vazio ou tipo inválido
VAL_CEP004 = "VAL_CEP004" # CEP sequencial ou com dígitos repetidos (ex: 11111-111, 12345-678)
VAL_CEP005 = "VAL_CEP005" # Formato básico inválido (não numérico, comprimento errado)
VAL_CEP006 = "VAL_CEP006" # Erro na consulta da API externa (timeout, serviço fora)

logger = logging.getLogger(__name__)

# Altera a herança para BaseValidator
class CEPValidator(BaseValidator):
    """
    Validador de Códigos de Endereçamento Postal (CEP) para o Brasil.
    Realiza validação de formato, verifica padrões comuns inválidos (sequenciais/repetidos)
    e simula consulta a uma API externa (como ViaCEP) para validação e enriquecimento.
    """

    # O construtor agora aceita db_manager e o passa para a classe base
    def __init__(self, db_manager: Optional[Any] = None): # <-- Modificado aqui
        super().__init__(origin_name="cep_validator", db_manager=db_manager) # <-- Modificado aqui
        logger.info("CEPValidator inicializado.")

    def _clean_cep(self, cep: str) -> str:
        """Remove caracteres não numéricos do CEP."""
        return re.sub(r'\D', '', cep)

    def _is_sequential_or_repeated(self, cleaned_cep: str) -> bool:
        """Verifica se o CEP tem 4 ou mais dígitos sequenciais ou repetidos."""
        if len(cleaned_cep) < 4:
            return False

        # Verifica sequenciais (ex: 1234, 5432)
        for i in range(len(cleaned_cep) - 3):
            subset = cleaned_cep[i:i+4]
            if all(d.isdigit() for d in subset):
                s0, s1, s2, s3 = int(subset[0]), int(subset[1]), int(subset[2]), int(subset[3])
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
        Simula a consulta à API ViaCEP.
        Em um ambiente real, faria uma requisição HTTP para 'https://viacep.com.br/ws/{cep}/json/'.
        """
        logger.debug(f"Simulando consulta à API ViaCEP para CEP: {cep}")
        await asyncio.sleep(0.05) # Simula um pequeno atraso de rede

        # Dados simulados para ViaCEP
        simulated_responses = {
            "01001000": {
                "cep": "01001-000",
                "logradouro": "Praça da Sé",
                "complemento": "lado ímpar",
                "bairro": "Sé",
                "localidade": "São Paulo",
                "uf": "SP",
                "ibge": "3550308",
                "gia": "1004",
                "ddd": "11",
                "siafi": "7107"
            },
            "20040003": {
                "cep": "20040-003",
                "logradouro": "Rua da Quitanda",
                "complemento": "",
                "bairro": "Centro",
                "localidade": "Rio de Janeiro",
                "uf": "RJ",
                "ibge": "3304557",
                "gia": "",
                "ddd": "21",
                "siafi": "6001"
            },
            "99999999": {"erro": True}, # CEP não encontrado
            "12345678": {"erro": True}, # Outro CEP não encontrado
            "88888888": {"erro": True}, # Sequencial, mas também não encontrado na simulação
        }

        response_data = simulated_responses.get(cep)
        
        # Simula erro de API (ex: timeout, serviço fora) para alguns CEPs
        if cep == "99999000": # Exemplo de CEP que simula erro de API
            logger.error(f"Simulando falha de API para o CEP: {cep}")
            raise Exception("Simulated API connection error or timeout.")

        return response_data

    # O método `validate` deve ser implementado conforme a interface do BaseValidator
    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]: # <-- Adicionado/Modificado para corresponder à interface
        """
        Valida um CEP (Código de Endereçamento Postal).
        Este é o método principal de validação exigido pela BaseValidator.

        Args:
            data (Any): O número do CEP a ser validado (pode conter formatação).
            **kwargs: Argumentos adicionais (não utilizados diretamente aqui, mas parte da interface).

        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação.
        """
        cep = str(data) # Garante que o input é uma string para processamento
        original_cep = cep
        cleaned_cep = self._clean_cep(cep)

        result = self._format_result( # <-- Usando o método _format_result da classe base
            is_valid=False,
            normalized_data=cleaned_cep,
            message="Falha na validação inicial do CEP.",
            details={"input_original": original_cep},
            business_rule_applied={"code": VAL_CEP005, "description": "Formato básico inválido"}
        )

        # 1. Verificação de Input Vazio ou Inválido
        if not isinstance(original_cep, str) or not original_cep.strip():
            result = self._format_result(
                is_valid=False,
                normalized_data=None,
                message="CEP vazio ou tipo inválido.",
                details={"input_original": original_cep},
                business_rule_applied={"code": VAL_CEP003, "description": "Input vazio ou tipo inválido"}
            )
            return result

        # 2. Verificação de Formato Básico e Comprimento
        if not cleaned_cep.isdigit() or len(cleaned_cep) != 8:
            result = self._format_result(
                is_valid=False,
                normalized_data=cleaned_cep,
                message="Formato de CEP inválido: deve conter exatamente 8 dígitos numéricos.",
                details={"input_original": original_cep},
                business_rule_applied={"code": VAL_CEP005, "description": "Formato básico inválido"}
            )
            return result

        # 3. Verificação de Padrões Sequenciais/Repetidos
        if self._is_sequential_or_repeated(cleaned_cep):
            result = self._format_result(
                is_valid=False,
                normalized_data=cleaned_cep,
                message="CEP inválido: contém dígitos sequenciais ou repetidos (e.g., 11111-111, 12345-678).",
                details={"input_original": original_cep},
                business_rule_applied={"code": VAL_CEP004, "description": "CEP sequencial ou com dígitos repetidos"}
            )
            return result

        # 4. Consulta à API Externa (simulada)
        api_data = None
        try:
            api_data = await self._consult_via_cep_api(cleaned_cep)
            
            if api_data and not api_data.get("erro"):
                result = self._format_result(
                    is_valid=True,
                    normalized_data=cleaned_cep,
                    message="CEP válido e encontrado na base externa (ViaCEP simulado).",
                    details={
                        "input_original": original_cep,
                        "address_found": True,
                        "external_api_data": api_data,
                        "external_api_response_raw": api_data # Manter a original também para depuração
                    },
                    business_rule_applied={"code": VAL_CEP001, "description": "CEP válido e encontrado"}
                )
            else:
                # O formato é válido, mas não foi encontrado na API
                result = self._format_result(
                    is_valid=True, # Consideramos válido no formato, mas não confirmável pela API
                    normalized_data=cleaned_cep,
                    message="CEP válido, mas não encontrado na base externa (ViaCEP simulado).",
                    details={
                        "input_original": original_cep,
                        "address_found": False,
                        "external_api_response_raw": api_data # Manter a original
                    },
                    business_rule_applied={"code": VAL_CEP002, "description": "CEP válido, mas não encontrado na API externa"}
                )

        except Exception as e:
            # Falha na API torna o resultado incerto ou inválido para processamento completo
            result = self._format_result(
                is_valid=False,
                normalized_data=cleaned_cep,
                message=f"Erro ao consultar API externa de CEP: {e}. Validação base pode estar comprometida.",
                details={
                    "input_original": original_cep,
                    "api_error": str(e)
                },
                business_rule_applied={"code": VAL_CEP006, "description": "Erro na consulta da API externa"}
            )
            logger.error(f"Erro na validação de CEP {cleaned_cep} via API externa: {e}", exc_info=True)

        logger.debug(f"Validação de CEP para '{original_cep}' (limpo: '{cleaned_cep}'): {result['mensagem']}")
        return result