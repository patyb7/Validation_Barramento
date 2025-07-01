# app/rules/pessoa/composite_validator.py
import logging
from typing import Dict, Any, List, Optional, Union, Tuple # Adicionada Tuple
from app.rules.base import BaseValidator
from app.rules.phone.validator import PhoneValidator
from app.rules.address.cep.validator import CEPValidator
from app.rules.email.validator import EmailValidator
from app.rules.document.cpf_cnpj.validator import CpfCnpjValidator
from app.rules.address.address_validator import AddressValidator
from app.rules.pessoa.nome.validator import NomeValidator
from app.rules.pessoa.genero.validator import SexoValidator
from app.rules.pessoa.rg.validator import RGValidator
from app.rules.pessoa.data_nascimento.validator import DataNascimentoValidator
# Importar o PersonDataModel para tipagem
from app.api.schemas.common import PersonDataModel # Corrigido de PersonDataMode

logger = logging.getLogger(__name__)

class PessoaFullValidacao(BaseValidator): # Classe renomeada
    """
    Validador composto para dados de pessoa, orquestrando a validação
    de múltiplos campos como nome, CPF, telefone, email, etc.
    """
    def __init__(
        self,
        phone_validator: PhoneValidator,
        cep_validator: CEPValidator,
        email_validator: EmailValidator,
        cpf_cnpj_validator: CpfCnpjValidator,
        address_validator: AddressValidator,
        nome_validator: NomeValidator,
        sexo_validator: SexoValidator,
        rg_validator: RGValidator,
        data_nascimento_validator: DataNascimentoValidator
    ):
        super().__init__(origin_name="person_composite_validator") # Manter o origin_name original ou atualizar se desejar
        self.phone_validator = phone_validator
        self.cep_validator = cep_validator
        self.email_validator = email_validator
        self.cpf_cnpj_validator = cpf_cnpj_validator
        self.address_validator = address_validator
        self.nome_validator = nome_validator
        self.sexo_validator = sexo_validator
        self.rg_validator = rg_validator
        self.data_nascimento_validator = data_nascimento_validator
        logger.info("PessoaFullValidacao inicializado.") # Log atualizado

    async def _perform_individual_validation(
        self,
        validator: BaseValidator,
        field_name: str,
        data_value: Any,
        results: Dict[str, Any],
        error_message_prefix: str,
        normalized_data_key: Optional[str] = None # Para casos onde a chave normalizada é diferente do field_name
    ) -> None:
        """
        Executa uma validação individual e atualiza o dicionário de resultados.
        """
        if data_value is not None:
            validation_result = await validator.validate(data_value)
            results["details"]["individual_validations"][field_name] = validation_result
            if not validation_result.get("is_valid"):
                results["is_valid"] = False
                results["details"]["errors_summary"].append(
                    f"{error_message_prefix}: {validation_result.get('mensagem', 'Inválido.')}"
                )
            else:
                key_to_use = normalized_data_key if normalized_data_key else field_name
                if validation_result.get("dado_normalizado") is not None:
                    results["normalized_data"][key_to_use] = validation_result.get("dado_normalizado")

    async def validate(self, data: Union[Dict[str, Any], PersonDataModel], **kwargs) -> Dict[str, Any]:
        """
        Valida um dicionário ou modelo Pydantic contendo múltiplos dados de uma pessoa.
        Retorna um resumo dos resultados de cada validação.
        """
        results = {
            "is_valid": True,
            "overall_message": "Validação de pessoa concluída.",
            "normalized_data": {},
            "details": {
                "individual_validations": {},
                "errors_summary": [] # Lista para acumular mensagens de erro específicas
            },
            "business_rule_applied": {
                "code": "RNT_PER001",
                "type": "Pessoa - Composto",
                "name": "Validação de Dados Completos de Pessoa"
            }
        }

        client_identifier = kwargs.get('client_identifier')

        # Centraliza o acesso aos dados convertendo para dicionário
        data_dict = data.model_dump() if isinstance(data, PersonDataModel) else data

        # Validação de Nome
        await self._perform_individual_validation(
            self.nome_validator, "nome", data_dict.get("nome"), results, "Nome"
        )

        # Validação de CPF
        await self._perform_individual_validation(
            self.cpf_cnpj_validator, "cpf", data_dict.get("cpf"), results, "CPF"
        )

        # Validação de RG
        await self._perform_individual_validation(
            self.rg_validator, "rg", data_dict.get("rg"), results, "RG"
        )

        # Validação de Data de Nascimento
        # Note: o campo no PersonDataModel é 'data_nascimento', seu código original usava 'data_nasc'
        # Ajustei para 'data_nascimento' para consistência com o modelo
        await self._perform_individual_validation(
            self.data_nascimento_validator, "data_nascimento", data_dict.get("data_nasc"), results, "Data de Nascimento"
        )

        # Validação de Gênero/Sexo
        await self._perform_individual_validation(
            self.sexo_validator, "sexo", data_dict.get("sexo"), results, "Gênero/Sexo"
        )

        # Validação de Email
        await self._perform_individual_validation(
            self.email_validator, "email", data_dict.get("email"), results, "Email"
        )

        # Validação de CEP
        await self._perform_individual_validation(
            self.cep_validator, "cep", data_dict.get("cep"), results, "CEP"
        )
        
        # Validação de Endereço Completo
        # Coleta todos os campos de endereço que o validador de endereço espera
        endereco_input = {
            "logradouro": data_dict.get("logradouro"),
            "numero": data_dict.get("numero"),
            "complemento": data_dict.get("complemento"), # Se houver
            "bairro": data_dict.get("bairro"),
            "cidade": data_dict.get("cidade"),
            "estado": data_dict.get("estado"),
            "cep": data_dict.get("cep") # Passa o CEP também para o validador de endereço
        }
        # Filtra valores None para evitar passar chaves com valor None para o validador
        endereco_input = {k: v for k, v in endereco_input.items() if v is not None}

        if endereco_input: # Verifica se há dados para validar o endereço
            address_result = await self.address_validator.validate(endereco_input)
            results["details"]["individual_validations"]["endereco"] = address_result
            if not address_result.get("is_valid"):
                results["is_valid"] = False
                results["details"]["errors_summary"].append(
                    f"Endereço: {address_result.get('mensagem', 'Inválido.')}"
                )
            else:
                results["normalized_data"]["endereco"] = address_result.get("dado_normalizado")

        # Validação de Telefone Fixo
        telefone_fixo = data_dict.get("telefone_fixo")
        if telefone_fixo is not None:
            phone_fixo_result = await self.phone_validator.validate(telefone_fixo, client_identifier=client_identifier)
            results["details"]["individual_validations"]["telefone_fixo"] = phone_fixo_result
            if not phone_fixo_result.get("is_valid"):
                results["is_valid"] = False
                results["details"]["errors_summary"].append(
                    f"Telefone Fixo: {phone_fixo_result.get('mensagem', 'Inválido.')}"
                )
            else:
                results["normalized_data"]["telefone_fixo"] = phone_fixo_result.get("dado_normalizado")

        # Validação de Celular
        celular = data_dict.get("celular")
        if celular is not None:
            celular_result = await self.phone_validator.validate(celular, client_identifier=client_identifier)
            results["details"]["individual_validations"]["celular"] = celular_result
            if not celular_result.get("is_valid"):
                results["is_valid"] = False
                results["details"]["errors_summary"].append(
                    f"Celular: {celular_result.get('mensagem', 'Inválido.')}"
                )
            else:
                results["normalized_data"]["celular"] = celular_result.get("dado_normalizado")
        
        # Consolida dado normalizado e define a mensagem geral
        if results["is_valid"]:
            results["overall_message"] = "Todos os dados de pessoa válidos."
        else:
            # Se a validação geral falhou, e há um summary de erros, use-o
            if results["details"]["errors_summary"]:
                results["overall_message"] = "Falha na validação de um ou mais campos: " + "; ".join(results["details"]["errors_summary"])
            else:
                results["overall_message"] = "Pelo menos um dado de pessoa falhou na validação."
        
        # Remove a lista de erros do 'details' se não for desejada no resultado final,
        # ou se você quiser que ela seja explícita apenas no log.
        # Caso contrário, ela será parte do `details` retornado.
        # del results["details"]["errors_summary"] 

        # Adiciona dado original ao resultado para consistência com o formato do BaseValidator
        original_data_formatted = data.model_dump() if isinstance(data, PersonDataModel) else data

        return self._format_result(
            is_valid=results["is_valid"],
            dado_original=original_data_formatted, # Mantenha o dado original formatado
            dado_normalizado=results["normalized_data"], # O dado normalizado será um dicionário
            mensagem=results["overall_message"],
            details=results["details"], # Inclui 'individual_validations' e 'errors_summary'
            business_rule_applied=results["business_rule_applied"]
        )