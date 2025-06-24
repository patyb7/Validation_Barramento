# app/rules/email/validator.py

import re
import logging
from typing import Dict, Any
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

    def __init__(self):
        super().__init__(origin_name="email_validator") # Inicializa o BaseValidator
        logger.info("EmailValidator inicializado.")

    async def validate(self, data: Any, check_temporary_domains: bool = True, **kwargs) -> Dict[str, Any]: # <--- MÉTODO PADRONIZADO 'validate'
        """
        Valida um endereço de e-mail aplicando uma sequência de regras.

        Args:
            data (Any): O endereço de e-mail a ser validado. Esperado uma string.
            check_temporary_domains (bool): Se deve verificar domínios de e-mail temporários/descartáveis.
            **kwargs: Parâmetros adicionais (compatibilidade com BaseValidator).

        Returns:
            Dict[str, Any]: Um dicionário com os detalhes da validação no formato padrão do BaseValidator:
                            - "is_valid" (bool): True se o e-mail é considerado válido, False caso contrário.
                            - "dado_normalizado" (str): O e-mail normalizado (minúsculas, sem espaços).
                            - "mensagem" (str): Mensagem explicativa do resultado da validação.
                            - "origem_validacao" (str): Fonte principal da validação.
                            - "details" (dict): Detalhes específicos da validação, incluindo:
                                - "input_data_original": O e-mail original submetido.
                                - "is_disposable": True se for um domínio de e-mail temporário/descartável.
                                - "is_blacklisted": True se o domínio estiver na lista negra.
                                - "validation_details": Dicionário para detalhes adicionais da validação.
                            - "business_rule_applied" (dict): Detalhes da regra de negócio aplicada.
        """
        email = data # 'data' é o endereço de email
        
        initial_details = {
            "input_original": email,
            "is_disposable": False,
            "is_blacklisted": False,
            "validation_details": {}
        }
        
        # 1. Normalização e Verificação de Input Vazio
        if not isinstance(email, str) or not email.strip():
            return self._format_result(
                is_valid=False,
                dado_normalizado=None,
                mensagem="Endereço de e-mail vazio ou tipo inválido.",
                details=initial_details,
                business_rule_applied={"code": RNE_EMPTY_OR_INVALID_INPUT, "type": "email"}
            )
        
        normalized_email = self._normalize_email(email)
        initial_details["input_data_cleaned"] = normalized_email

        # Extrai o domínio para verificações posteriores
        domain_match = re.search(r'@([^@]+)$', normalized_email)
        domain = domain_match.group(1).lower() if domain_match else ""

        if not domain: # Se não encontrou um domínio, o formato é inválido
            return self._format_result(
                is_valid=False,
                dado_normalizado=normalized_email,
                mensagem="Endereço de e-mail com formato básico inválido: domínio ausente.",
                details=initial_details,
                business_rule_applied={"code": RNE_INVALID_FORMAT, "type": "email"}
            )

        # 2. Validação da Sintaxe e Domínio (com fallback)
        is_syntax_valid = False
        is_domain_valid = False
        message = ""
        
        if EMAIL_VALIDATOR_AVAILABLE:
            try:
                valid_email_info = validate_email(normalized_email, check_deliverability=True)
                is_syntax_valid = True
                is_domain_valid = True
                message = "E-mail válido (verificado por biblioteca)."
                initial_details["validation_details"]["email_validator_info"] = valid_email_info.as_dict()
                initial_details["validation_details"]["is_syntax_valid"] = True
                initial_details["validation_details"]["domain_resolves"] = True

            except EmailNotValidError as e:
                message = f"E-mail inválido: {e}"
                initial_details["validation_details"]["email_validator_error"] = str(e)
                if "domain" in str(e):
                    is_domain_valid = False
                    initial_details["validation_details"]["domain_resolves"] = False
                else:
                    is_syntax_valid = False
                    initial_details["validation_details"]["is_syntax_valid"] = False
                
                return self._format_result(
                    is_valid=False,
                    dado_normalizado=normalized_email,
                    mensagem=message,
                    details=initial_details,
                    business_rule_applied={"code": RNE_INVALID_FORMAT, "type": "email"}
                )
            except Exception as e:
                logger.error(f"Erro inesperado com 'email_validator' para '{normalized_email}': {e}", exc_info=True)
                message = f"Erro interno na validação de e-mail: {e}"
                initial_details["validation_details"]["unexpected_error"] = str(e)
                is_syntax_valid = re.match(r"[^@]+@[^@]+\.[^@]+", normalized_email) is not None
                is_domain_valid = True # Assume válido para prosseguir com blacklists
                
        if not EMAIL_VALIDATOR_AVAILABLE or not is_syntax_valid or not is_domain_valid:
            is_syntax_valid = re.match(r"[^@]+@[^@]+\.[^@]+", normalized_email) is not None
            initial_details["validation_details"]["is_syntax_valid_regex"] = is_syntax_valid
            if not is_syntax_valid:
                return self._format_result(
                    is_valid=False,
                    dado_normalizado=normalized_email,
                    mensagem="Formato de e-mail inválido (regex).",
                    details=initial_details,
                    business_rule_applied={"code": RNE_INVALID_FORMAT, "type": "email"}
                )
            if not is_domain_valid and EMAIL_VALIDATOR_AVAILABLE:
                message = "E-mail válido, mas domínio não pôde ser resolvido por API externa (fallback)."
                is_domain_valid = True 
            else:
                 message = "E-mail válido (verificação básica), prosseguindo com blacklists."

        # 3. Verificação de Domínios Temporários/Descartáveis
        if check_temporary_domains and domain in BLACKLISTED_DOMAINS:
            initial_details["is_disposable"] = True
            return self._format_result(
                is_valid=False,
                dado_normalizado=normalized_email,
                mensagem="E-mail inválido: domínio de e-mail temporário/descartável.",
                details=initial_details,
                business_rule_applied={"code": RNE_TEMPORARY_DOMAIN, "type": "email"}
            )
        
        # 4. Verificação de Whitelist (se houver e for restritiva)
        if WHITELISTED_DOMAINS and domain not in WHITELISTED_DOMAINS:
            initial_details["is_whitelisted"] = False
        elif WHITELISTED_DOMAINS: 
            initial_details["is_whitelisted"] = True
            
        return self._format_result(
            is_valid=True,
            dado_normalizado=normalized_email,
            mensagem=message,
            details=initial_details,
            business_rule_applied={"code": RNE_VALID_DOMAIN, "type": "email"} 
        )
    
    def _normalize_email(self, email: str) -> str:
        """Normaliza o endereço de e-mail para minúsculas e remove espaços em branco extras."""
        return email.strip().lower()
