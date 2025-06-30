# app/rules/email/validator.py

import re
import logging
from typing import Dict, Any, Optional # Importa Optional para db_manager
import asyncio # Importa asyncio, caso precise de sleeps ou awaits internos

from app.rules.base import BaseValidator # Importa BaseValidator

logger = logging.getLogger(__name__)

# Códigos de Regra específicos para validação de e-mail
RNE_VALID_SYNTAX = "RNE001"        # Sintaxe básica válida
RNE_VALID_DOMAIN = "RNE002"        # Domínio válido (MX record, etc. - via email_validator)
RNE_INVALID_FORMAT = "RNE003"      # Formato geral inválido (regex ou lib)
RNE_TEMPORARY_DOMAIN = "RNE004"    # Domínio de e-mail temporário/descartável
RNE_BLACK_LISTED_DOMAIN = "RNE005" # Domínio na lista negra
RNE_WHITELISTED_DOMAIN = "RNE006" # Domínio na lista branca (e a whitelist está ativa e é restritiva)
RNE_EMPTY_OR_INVALID_INPUT = "RNE007" # Input vazio ou tipo inválido

# --- Configuração e carregamento da biblioteca email_validator ---
EMAIL_VALIDATOR_AVAILABLE = True
try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:
    EMAIL_VALIDATOR_AVAILABLE = False
    logger.warning("A biblioteca 'email_validator' não está instalada. A validação de e-mail será básica (apenas regex e blacklists).")
except Exception as e:
    EMAIL_VALIDATOR_AVAILABLE = False
    logger.error(f"Erro inesperado ao carregar ou configurar email_validator: {e}. Desativando.")

# --- Regras em Memória (Fallback e Heurísticas) ---
# Você pode expandir estas listas conforme necessário
BLACKLISTED_DOMAINS = {
    "mailinator.com", "tempmail.com", "yopmail.com", "guerrillail.com", # Exemplos de domínios de e-mails temporários/descartáveis
    # Adicione outros domínios conhecidos por spam ou fraude aqui
}

WHITELISTED_DOMAINS = {
    # "suaempresa.com.br", "parceiro.com" # Exemplo: apenas e-mails destes domínios são permitidos
}

class EmailValidator(BaseValidator): # Herda de BaseValidator
    """
    Validador de endereços de e-mail com regras e fallback.
    Utiliza a biblioteca 'email_validator' para validação robusta
    e inclui regras em memória (regex, blacklists) para cenários específicos
    ou quando a biblioteca principal não está disponível.
    """

    # --- MODIFICAÇÃO CHAVE AQUI: Adicione db_manager ao __init__ ---
    def __init__(self, db_manager: Optional[Any] = None): 
        super().__init__(origin_name="email_validator", db_manager=db_manager) # Passa db_manager para o BaseValidator
        logger.info("EmailValidator inicializado.")

    # --- MODIFICAÇÃO CHAVE AQUI: Torne o método validate assíncrono ---
    async def validate(self, data: Any, **kwargs) -> Dict[str, Any]: # data é o input, kwargs para flexibilidade
        """
        Valida um endereço de e-mail aplicando uma sequência de regras.

        Args:
            data (Any): O endereço de e-mail a ser validado.
            **kwargs: Argumentos adicionais (e.g., check_temporary_domains).

        Returns:
            Dict[str, Any]: Um dicionário com os detalhes da validação no formato padrão do BaseValidator.
        """
        email = str(data).strip() if data is not None else ""
        original_email = email
        check_temporary_domains = kwargs.get("check_temporary_domains", True) # Pega do kwargs ou usa default

        initial_details = {
            "input_data_original": original_email, # Usar original_email aqui para o input original
            "is_disposable": False,
            "is_blacklisted": False,
            "validation_details": {}
        }
        
        # 1. Normalização e Verificação de Input Vazio
        if not isinstance(original_email, str) or not original_email.strip():
            return self._format_result(
                is_valid=False,
                normalized_data=None,
                message="Endereço de e-mail vazio ou tipo inválido.",
                details=initial_details,
                business_rule_applied={"code": RNE_EMPTY_OR_INVALID_INPUT, "type": "email"}
            )
        
        normalized_email = self._normalize_email(original_email) # Normaliza o original_email
        initial_details["input_data_cleaned"] = normalized_email

        # Extrai o domínio para verificações posteriores
        domain_match = re.search(r'@([^@]+)$', normalized_email)
        domain = domain_match.group(1).lower() if domain_match else ""

        if not domain: # Se não encontrou um domínio, o formato é inválido
            return self._format_result(
                is_valid=False,
                normalized_data=normalized_email,
                message="Endereço de e-mail com formato básico inválido: domínio ausente.",
                details=initial_details,
                business_rule_applied={"code": RNE_INVALID_FORMAT, "type": "email"}
            )

        # 2. Verifica Whitelisted Domains (se aplicável, com prioridade máxima)
        if WHITELISTED_DOMAINS and domain not in WHITELISTED_DOMAINS:
            return self._format_result(
                is_valid=False,
                normalized_data=normalized_email,
                message=f"Domínio '{domain}' não está na lista branca permitida.",
                details=initial_details,
                business_rule_applied={"code": RNE_WHITELISTED_DOMAIN, "type": "email"}
            )
        
        # 3. Verifica Blacklisted/Temporary Domains (prioridade alta)
        if check_temporary_domains and domain in BLACKLISTED_DOMAINS:
            initial_details["is_blacklisted"] = True
            initial_details["is_disposable"] = True 
            return self._format_result(
                is_valid=False,
                normalized_data=normalized_email,
                message=f"Domínio '{domain}' é um domínio de e-mail temporário/descartável ou está na lista negra.",
                details=initial_details,
                business_rule_applied={"code": RNE_BLACK_LISTED_DOMAIN, "type": "email"}
            )

        # 4. Validação Principal com email_validator (se disponível)
        if EMAIL_VALIDATOR_AVAILABLE:
            try:
                # `check_deliverability=False` para evitar consultas DNS lentas na simulação
                email_info = validate_email(normalized_email, check_deliverability=False) 
                
                initial_details["validation_details"]["email_info"] = email_info.as_dict() 
                logger.debug(f"Validação de e-mail: '{normalized_email}' válido via email_validator.")
                return self._format_result(
                    is_valid=True,
                    normalized_data=normalized_email,
                    message="Endereço de e-mail válido (via email_validator).",
                    details=initial_details,
                    business_rule_applied={"code": RNE_VALID_SYNTAX, "type": "email"}
                )

            except EmailNotValidError as e:
                logger.debug(f"Validação de e-mail: '{normalized_email}' inválido via email_validator: {e}")
            except Exception as e:
                logger.error(f"Validação de e-mail: Erro fatal com email_validator para '{normalized_email}': {e}", exc_info=True)

        # 5. Validação de Fallback (Regex)
        email_regex = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
        if email_regex.fullmatch(normalized_email):
            logger.debug(f"Validação de e-mail: '{normalized_email}' válido via fallback regex.")
            return self._format_result(
                is_valid=True,
                normalized_data=normalized_email,
                message="Endereço de e-mail válido (via fallback regex).",
                details=initial_details,
                business_rule_applied={"code": RNE_VALID_SYNTAX, "type": "email"}
            )
        else:
            logger.debug(f"Validação de e-mail: '{normalized_email}' inválido via fallback regex.")
            return self._format_result(
                is_valid=False,
                normalized_data=normalized_email,
                message="Endereço de e-mail com formato inválido (via fallback regex).",
                details=initial_details,
                business_rule_applied={"code": RNE_INVALID_FORMAT, "type": "email"}
            )

    def _normalize_email(self, email: str) -> str:
        """
        Normaliza o endereço de e-mail: remove espaços em branco e converte para minúsculas.
        """
        if not email:
            return ""
        return email.strip().lower()