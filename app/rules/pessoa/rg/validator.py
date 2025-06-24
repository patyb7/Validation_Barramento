# app/rules/pssoa/rg/validator.py

import re
import logging
from typing import Dict, Any, Optional
from app.rules.base import BaseValidator

logger = logging.getLogger(__name__)

class RGValidator(BaseValidator):
    """
    Validador para números de Registro Geral (RG) em um formato simplificado.
    Realiza validação de formato e comprimento, e simula uma consulta a uma base cadastral.
    """
    # Códigos de Regra específicos para validação de RG (Padronização RN_RGxxx)
    RN_RG001 = "RN_RG001"  # RG Válido e Ativo
    RN_RG002 = "RN_RG002"  # Formato de RG inválido (não é numérico, ou comprimento incorreto)
    RN_RG003 = "RN_RG003"  # RG com dígito verificador inválido (se aplicável, para RGs mais complexos) - SIMULADO
    RN_RG004 = "RN_RG004"  # RG com todos os dígitos iguais (ex: 11.111.111-1)
    RN_RG005 = "RN_RG005"  # RG válido (formato/checksum), mas inativo/suspenso na base cadastral
    RN_RG006 = "RN_RG006"  # RG válido (formato/checksum), mas não encontrado na base cadastral
    RN_RG007 = "RN_RG007"  # Input vazio ou tipo inválido (não string, ou string vazia)

    def __init__(self):
        super().__init__(origin_name="rg_validator")
        logger.info("RGValidator inicializado.")
        # Simulação de uma base de dados cadastral de RGs
        self.simulated_rg_database = {
            "346913500": {"name": "Marcos Lucca Danilo Galvão", "status": "ATIVO", "is_active": True},
            "168074485": {"name": "Lara Amanda Fernandes", "status": "BLOQUEADO", "is_active": False},
            "111111111": {"name": "RG Sequencial Inválido", "status": None, "is_active": False},
        }

    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Valida um número de RG, verificando formato e consultando uma base de dados cadastral simulada.

        Args:
            data (Any): O número do RG a ser validado. Esperado uma string.
            **kwargs: Parâmetros adicionais (compatibilidade com BaseValidator).

        Returns:
            Dict[str, Any]: Um dicionário com o resultado da validação padronizado.
        """
        rg_number = data
        logger.info(f"Iniciando validação de RG: {rg_number[:5] if isinstance(rg_number, str) and len(rg_number) > 5 else rg_number}...")

        # 1. Verificação de Input Vazio ou Inválido
        if not isinstance(rg_number, str) or not rg_number.strip():
            return self._format_result(
                is_valid=False,
                dado_original=rg_number, # Adicionado dado_original
                dado_normalizado=None,
                mensagem="RG vazio ou tipo inválido.",
                details={"input_original": rg_number},
                business_rule_applied={"code": self.RN_RG007, "type": "RG - Validação Primária", "name": "Input de RG Vazio ou Inválido"}
            )

        normalized_rg = self._normalize_rg(rg_number)
        is_valid_format = False
        validation_message = "RG inválido."
        business_rule_code = self.RN_RG002 # Default para formato inválido
        
        details = {
            "input_original": rg_number,
            "normalized_rg": normalized_rg,
            "is_valid_format": False,
            "is_valid_checksum": False, # RG simplificado não calcula checksum, mas mantém para consistência
            "simulated_db_status": None,
            "is_active_in_database": False,
            "customer_name": None,
            "reason": []
        }

        # Validação de formato básico (números e comprimento típico)
        # Assumindo RGs de 8 ou 9 dígitos para esta simulação (ex: 12.345.678-9)
        if re.fullmatch(r'^\d{8,9}$', normalized_rg):
            is_valid_format = True
            details["is_valid_format"] = True
            if len(set(normalized_rg)) == 1:
                validation_message = "RG inválido: todos os dígitos são iguais."
                business_rule_code = self.RN_RG004
                details["reason"].append("all_digits_same")
            else:
                # Simular validação de checksum, mesmo que não seja implementado o cálculo real
                # Assumimos que o formato básico significa que o "checksum" está OK para prosseguir para a DB
                details["is_valid_checksum"] = True
                validation_message = "RG com formato válido."
                business_rule_code = self.RN_RG001 # Assume válido até checar DB
        else:
            validation_message = "Formato de RG inválido (comprimento ou caracteres incorretos)."
            business_rule_code = self.RN_RG002
            details["reason"].append("invalid_format")

        # Se o formato for inválido, retorna imediatamente
        if not is_valid_format or business_rule_code == self.RN_RG004:
            return self._format_result(
                is_valid=False,
                dado_original=rg_number, # Adicionado dado_original
                dado_normalizado=normalized_rg,
                mensagem=validation_message,
                details=details,
                business_rule_applied={"code": business_rule_code, "type": "RG - Validação Primária", "name": validation_message}
            )

        # Se o formato e checksum (simulado) forem válidos, prossegue para a consulta na base de dados
        logger.info(f"RG com formato válido. Consultando base de dados cadastral simulada para RG: {normalized_rg}")
        customer_data = self.simulated_rg_database.get(normalized_rg)

        is_valid_final = False
        if customer_data:
            details["simulated_db_status"] = "Found"
            details["is_active_in_database"] = customer_data.get("is_active", False)
            details["customer_name"] = customer_data.get("name")
            if details["is_active_in_database"]:
                validation_message = "RG válido e ativo na base cadastral."
                is_valid_final = True
                business_rule_code = self.RN_RG001
            else:
                validation_message = f"RG válido, mas inativo/suspenso na base cadastral (status: {customer_data.get('status')})."
                is_valid_final = False
                business_rule_code = self.RN_RG005
                details["reason"].append("rg_inactive_in_database")
        else:
            validation_message = "RG válido (formato), mas não encontrado na base cadastral simulada."
            is_valid_final = False
            business_rule_code = self.RN_RG006
            details["reason"].append("rg_not_found_in_database")
            
        return self._format_result(
            is_valid=is_valid_final,
            dado_original=rg_number, # Adicionado dado_original
            dado_normalizado=normalized_rg,
            mensagem=validation_message,
            details=details,
            business_rule_applied={"code": business_rule_code, "type": "RG - Validação Final", "name": validation_message}
        )

    def _normalize_rg(self, rg: str) -> str:
        """Remove caracteres não numéricos do RG."""
        if not rg:
            return ""
        # Remove pontos, traços e outros caracteres não numéricos
        return re.sub(r'\D', '', str(rg))
