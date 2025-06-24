import logging
from typing import Dict, Any, List, Optional, Union # Adicionada Union
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
                "individual_validations": {}
            },
            "business_rule_applied": {
                "code": "RNT_PER001",
                "type": "Pessoa - Composto",
                "name": "Validação de Dados Completos de Pessoa"
            }
        }

        # Extrai o client_identifier, se disponível nos kwargs
        client_identifier = kwargs.get('client_identifier')

        # Converte para dicionário se for um modelo Pydantic para acesso uniforme
        # No entanto, vamos preferir acessar como atributo e usar getattr para segurança
        # data_dict = data.model_dump() if isinstance(data, BaseModel) else data

        # Validação de Nome
        # Acessa como atributo, com fallback para None se não existir
        nome = getattr(data, "nome", None)
        if nome is not None:
            nome_result = await self.nome_validator.validate(nome)
            results["details"]["individual_validations"]["nome"] = nome_result
            if not nome_result.get("is_valid"):
                results["is_valid"] = False
                results["overall_message"] = "Validação de nome falhou."
            else:
                results["normalized_data"]["nome"] = nome_result.get("dado_normalizado")


        # Validação de CPF
        cpf = getattr(data, "cpf", None)
        if cpf is not None:
            cpf_result = await self.cpf_cnpj_validator.validate(cpf)
            results["details"]["individual_validations"]["cpf"] = cpf_result
            if not cpf_result.get("is_valid"):
                results["is_valid"] = False
                results["overall_message"] = "Validação de CPF falhou."
            else:
                results["normalized_data"]["cpf"] = cpf_result.get("dado_normalizado")


        # Validação de RG
        rg = getattr(data, "rg", None)
        if rg is not None:
            rg_result = await self.rg_validator.validate(rg)
            results["details"]["individual_validations"]["rg"] = rg_result
            if not rg_result.get("is_valid"):
                results["is_valid"] = False
                results["overall_message"] = "Validação de RG falhou."
            else:
                results["normalized_data"]["rg"] = rg_result.get("dado_normalizado")

        # Validação de Data de Nascimento
        data_nasc = getattr(data, "data_nasc", None)
        if data_nasc is not None:
            data_nasc_result = await self.data_nascimento_validator.validate(data_nasc)
            results["details"]["individual_validations"]["data_nascimento"] = data_nasc_result
            if not data_nasc_result.get("is_valid"):
                results["is_valid"] = False
                results["overall_message"] = "Validação de data de nascimento falhou."
            else:
                results["normalized_data"]["data_nascimento"] = data_nasc_result.get("dado_normalizado")

        # Validação de Gênero/Sexo
        sexo = getattr(data, "sexo", None)
        if sexo is not None:
            sexo_result = await self.sexo_validator.validate(sexo)
            results["details"]["individual_validations"]["sexo"] = sexo_result
            if not sexo_result.get("is_valid"):
                results["is_valid"] = False
                results["overall_message"] = "Validação de gênero/sexo falhou."
            else:
                results["normalized_data"]["sexo"] = sexo_result.get("dado_normalizado")

        # Validação de Email
        email = getattr(data, "email", None)
        if email is not None:
            email_result = await self.email_validator.validate(email)
            results["details"]["individual_validations"]["email"] = email_result
            if not email_result.get("is_valid"):
                results["is_valid"] = False
                results["overall_message"] = "Validação de email falhou."
            else:
                results["normalized_data"]["email"] = email_result.get("dado_normalizado")

        # Validação de CEP
        cep = getattr(data, "cep", None)
        if cep is not None:
            cep_result = await self.cep_validator.validate(cep)
            results["details"]["individual_validations"]["cep"] = cep_result
            if not cep_result.get("is_valid"):
                results["is_valid"] = False
                results["overall_message"] = "Validação de CEP falhou."
            else:
                results["normalized_data"]["cep"] = cep_result.get("dado_normalizado")

        # Validação de Endereço (pode precisar de mais campos do dict)
        endereco_completo = {
            "logradouro": getattr(data, "endereco", None),
            "numero": getattr(data, "numero", None),
            "bairro": getattr(data, "bairro", None),
            "cidade": getattr(data, "cidade", None),
            "estado": getattr(data, "estado", None),
            "cep": getattr(data, "cep", None) # Passa o CEP também para o validador de endereço
        }
        # Filtra valores None para evitar erros nos validadores downstream se não esperarem None
        endereco_completo = {k: v for k, v in endereco_completo.items() if v is not None}

        if endereco_completo: # Verifica se há dados para validar o endereço
            address_result = await self.address_validator.validate(endereco_completo)
            results["details"]["individual_validations"]["endereco"] = address_result
            if not address_result.get("is_valid"):
                results["is_valid"] = False
                results["overall_message"] = "Validação de endereço falhou."
            else:
                results["normalized_data"]["endereco"] = address_result.get("dado_normalizado")


        # Validação de Telefone Fixo
        telefone_fixo = getattr(data, "telefone_fixo", None)
        if telefone_fixo is not None:
            # Passa o client_identifier para o validador de telefone, se existir
            phone_fixo_result = await self.phone_validator.validate(telefone_fixo, client_identifier=client_identifier)
            results["details"]["individual_validations"]["telefone_fixo"] = phone_fixo_result
            if not phone_fixo_result.get("is_valid"):
                results["is_valid"] = False
                results["overall_message"] = "Validação de telefone fixo falhou."
            else:
                results["normalized_data"]["telefone_fixo"] = phone_fixo_result.get("dado_normalizado")

        # Validação de Celular
        celular = getattr(data, "celular", None)
        if celular is not None:
            # Passa o client_identifier para o validador de telefone, se existir
            celular_result = await self.phone_validator.validate(celular, client_identifier=client_identifier)
            results["details"]["individual_validations"]["celular"] = celular_result
            if not celular_result.get("is_valid"):
                results["is_valid"] = False
                results["overall_message"] = "Validação de celular falhou."
            else:
                results["normalized_data"]["celular"] = celular_result.get("dado_normalizado")
        
        # Consolida dado normalizado (opcional, pode ser o CPF normalizado ou uma combinação)
        if results["is_valid"] and results["overall_message"] == "Validação de pessoa concluída.":
            results["overall_message"] = "Todos os dados de pessoa válidos."
        elif not results["is_valid"] and results["overall_message"] == "Validação de pessoa concluída.":
             # Se a validação geral falhou e a mensagem não foi atualizada por um sub-validador
             results["overall_message"] = "Pelo menos um dado de pessoa falhou na validação."


        # Adiciona dado original ao resultado para consistência com o formato do BaseValidator
        # Garante que dado_original seja um dicionário ou string, não um modelo Pydantic
        original_data_formatted = data.model_dump() if isinstance(data, PersonDataModel) else data

        return self._format_result(
            is_valid=results["is_valid"],
            dado_original=original_data_formatted, # Mantenha o dado original formatado
            dado_normalizado=results["normalized_data"], # O dado normalizado será um dicionário
            mensagem=results["overall_message"],
            details=results["details"],
            business_rule_applied=results["business_rule_applied"]
        )
