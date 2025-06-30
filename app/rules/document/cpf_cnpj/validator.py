import logging
import re
from typing import Dict, Any, Optional, Union
from app.rules.base import BaseValidator # Ensure this import is correct
import asyncio # Importa asyncio para métodos assíncronos

logger = logging.getLogger(__name__)

# Códigos de Regra específicos para validação de CPF/CNPJ
VAL_DOC001 = "VAL_DOC001" # Documento válido e ativo
VAL_DOC002 = "VAL_DOC002" # Formato de documento inválido (não é CPF nem CNPJ)
VAL_DOC003 = "VAL_DOC003" # CPF/CNPJ com dígitos verificadores inválidos
VAL_DOC004 = "VAL_DOC004" # CPF/CNPJ com todos os dígitos iguais (ex: 111.111.111-11)
VAL_DOC005 = "VAL_DOC005" # Documento válido (checksum), mas inativo/suspenso na base cadastral
VAL_DOC006 = "VAL_DOC006" # Documento válido (checksum), mas não encontrado na base cadastral
VAL_DOC007 = "VAL_DOC007" # Input vazio ou tipo inválido


class CpfCnpjValidator(BaseValidator): # Inherit from BaseValidator
    """
    Validador para documentos CPF e CNPJ.
    Realiza a validação do formato e checksum, e simula uma consulta
    a uma base de dados cadastral de clientes para verificar o status.
    """

    # --- MODIFICAÇÃO AQUI: Adicione db_manager ao __init__ ---
    def __init__(self, db_manager: Optional[Any] = None):
        super().__init__(origin_name="CpfCnpjValidator", db_manager=db_manager) # Passa db_manager para o BaseValidator
        logger.info("CpfCnpjValidator inicializado.")
        # Simulação de uma base de dados cadastral de clientes
        self.simulated_customer_database = {
            "11122233344": {"name": "Cliente Exemplo CPF Válido", "status_receita_federal": "REGULAR", "is_active": True},
            "55566677788": {"name": "Cliente Exemplo CPF Irregular", "status_receita_federal": "SUSPENSO", "is_active": False},
            "00000000000": {"name": "CPF Sequencial Inválido", "status_receita_federal": None, "is_active": False}, # Exemplo de CPF inválido por algoritmo
            "12345678000190": {"name": "Empresa Teste CNPJ Válido", "status_receita_federal": "ATIVA", "is_active": True},
            "98765432000121": {"name": "Empresa Teste CNPJ Baixada", "status_receita_federal": "BAIXADA", "is_active": False},
            "11111111111111": {"name": "CNPJ Sequencial Inválido", "status_receita_federal": None, "is_active": False}, # Exemplo de CNPJ inválido por algoritmo
        }

    # --- MODIFICAÇÃO CHAVE AQUI: Renomeie e adapte para 'validate' ---
    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Valida um número de CPF ou CNPJ, verificando formato, checksum e consultando
        uma base de dados cadastral simulada.

        Args:
            data (Any): O número do CPF ou CNPJ a ser validado.
            **kwargs: Argumentos adicionais (atualmente não usados, mas para conformidade).

        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação no formato padrão do BaseValidator.
        """
        document_number = str(data).strip() if data is not None else "" # Extrai o dado do 'data'

        logger.info(f"Iniciando validação de documento: {document_number[:5]}...")

        # 1. Verificação de Input Vazio ou Inválido
        if not isinstance(document_number, str) or not document_number.strip():
            return self._format_result(
                is_valid=False,
                normalized_data=None, # Use normalized_data em vez de dado_normalizado
                message="Documento vazio ou tipo inválido.",
                details={"input_original": document_number},
                business_rule_applied={"code": VAL_DOC007, "type": "cpf_cnpj"}
            )

        normalized_document = self._normalize_document(document_number)
        is_cpf = len(normalized_document) == 11
        is_cnpj = len(normalized_document) == 14

        is_valid_format = False
        is_valid_checksum = False
        document_type = None
        status_cadastro = None
        is_active_in_db = False
        customer_name = None
        
        validation_message = "Documento inválido."
        business_rule_code = VAL_DOC002 # Default for invalid format
        
        details = {
            "document_type": None,
            "is_valid_checksum": False,
            "status_receita_federal": None,
            "is_active_in_database": False,
            "customer_name": None,
            "reason": []
        }

        if is_cpf:
            document_type = "CPF"
            is_valid_format = True
            details["document_type"] = "CPF"
            
            if len(set(normalized_document)) == 1:
                validation_message = "CPF inválido: todos os dígitos são iguais."
                business_rule_code = VAL_DOC004
                details["reason"].append("all_digits_same")
            else:
                is_valid_checksum = self._validate_cpf_checksum(normalized_document)
                details["is_valid_checksum"] = is_valid_checksum
                if not is_valid_checksum:
                    validation_message = "CPF com dígitos verificadores inválidos."
                    business_rule_code = VAL_DOC003
                    details["reason"].append("invalid_cpf_checksum")
                
        elif is_cnpj:
            document_type = "CNPJ"
            is_valid_format = True
            details["document_type"] = "CNPJ"

            if len(set(normalized_document)) == 1:
                validation_message = "CNPJ inválido: todos os dígitos são iguais."
                business_rule_code = VAL_DOC004
                details["reason"].append("all_digits_same")
            else:
                is_valid_checksum = self._validate_cnpj_checksum(normalized_document)
                details["is_valid_checksum"] = is_valid_checksum
                if not is_valid_checksum:
                    validation_message = "CNPJ com dígitos verificadores inválidos."
                    business_rule_code = VAL_DOC003
                    details["reason"].append("invalid_cnpj_checksum")
        else:
            validation_message = "Formato de documento inválido (não é CPF nem CNPJ)."
            business_rule_code = VAL_DOC002
            details["reason"].append("invalid_document_format")
            
        # If format or checksum are invalid, no need to consult the database
        if not is_valid_format or not is_valid_checksum:
            return self._format_result(
                is_valid=False,
                normalized_data=normalized_document, # Use normalized_data
                message=validation_message,
                details=details,
                business_rule_applied={"code": business_rule_code, "type": "cpf_cnpj"}
            )

        # Simulate querying the customer database
        logger.debug(f"Consultando base de clientes para {document_type}: {normalized_document}")
        customer_data = self.simulated_customer_database.get(normalized_document)

        if customer_data:
            status_cadastro = customer_data.get("status_receita_federal")
            is_active_in_db = customer_data.get("is_active", False)
            customer_name = customer_data.get("name")

            details["status_receita_federal"] = status_cadastro
            details["is_active_in_database"] = is_active_in_db
            details["customer_name"] = customer_name

            if is_active_in_db:
                validation_message = f"{document_type} válido e ativo na base cadastral."
                is_valid = True
                business_rule_code = VAL_DOC001
            else:
                validation_message = f"{document_type} válido, mas inativo/suspenso na base cadastral (status: {status_cadastro})."
                is_valid = False
                business_rule_code = VAL_DOC005
                details["reason"].append("document_inactive_in_database")
        else:
            validation_message = f"{document_type} válido (checksum), mas não encontrado na base cadastral."
            is_valid = False
            business_rule_code = VAL_DOC006
            details["reason"].append("document_not_found_in_database")
            
        return self._format_result(
            is_valid=is_valid,
            normalized_data=normalized_document, # Use normalized_data
            message=validation_message,
            details=details,
            business_rule_applied={"code": business_rule_code, "type": "cpf_cnpj"}
        )

    def _normalize_document(self, document: str) -> str:
        """Remove caracteres não numéricos do documento."""
        if not document:
            return ""
        return re.sub(r'[^0-9]', '', str(document))

    def _validate_cpf_checksum(self, cpf: str) -> bool:
        """Valida o checksum de um CPF."""
        if not re.fullmatch(r'\d{11}', cpf):
            return False

        def calculate_digit(cpf_part: str, weight_start: int) -> int:
            total_sum = 0
            for i, digit in enumerate(cpf_part):
                total_sum += int(digit) * (weight_start - i)
            remainder = total_sum % 11
            return 0 if remainder < 2 else 11 - remainder

        # Primeiro dígito verificador
        digit1 = calculate_digit(cpf[:9], 10)
        if digit1 != int(cpf[9]):
            return False

        # Segundo dígito verificador
        digit2 = calculate_digit(cpf[:10], 11)
        if digit2 != int(cpf[10]):
            return False

        return True

    def _validate_cnpj_checksum(self, cnpj: str) -> bool:
        """Valida o checksum de um CNPJ."""
        if not re.fullmatch(r'\d{14}', cnpj):
            return False

        def calculate_digit(cnpj_part: str, weights: list) -> int:
            total_sum = 0
            for i in range(len(cnpj_part)):
                total_sum += int(cnpj_part[i]) * weights[i]
            remainder = total_sum % 11
            return 0 if remainder < 2 else 11 - remainder

        # Pesos para o primeiro dígito verificador
        weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        digit1 = calculate_digit(cnpj[:12], weights1)
        if digit1 != int(cnpj[12]):
            return False

        # Pesos para o segundo dígito verificador
        weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        digit2 = calculate_digit(cnpj[:13], weights2)
        if digit2 != int(cnpj[13]):
            return False

        return True