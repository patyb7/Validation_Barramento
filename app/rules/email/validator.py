# app/rules/email/validator.py

import re
import logging
from typing import Dict, Any, Optional

from app.rules.base import BaseValidator

logger = logging.getLogger(__name__)

# --- Configuração e carregamento da biblioteca email_validator ---
EMAIL_VALIDATOR_AVAILABLE = True
try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:
    EMAIL_VALIDATOR_AVAILABLE = False
    logger.warning("A biblioteca 'email_validator' não está instalada. A validação de e-mail será básica (apenas regex e blacklists).")
except Exception as e:
    EMAIL_VALIDATOR_AVAILABLE = False
    logger.error(f"Erro inesperado ao carregar ou configurar email_validator: {e}. Desativando.", exc_info=True)

# --- Regras em Memória (Fallback e Heurísticas) ---
# Você pode expandir estas listas conforme necessário
# ATENÇÃO: BLACKLISTED_DOMAINS deve conter APENAS domínios que você deseja explicitamente bloquear.
# Domínios temporários/descartáveis são tratados separadamente ou podem ser incluídos aqui se for o caso.
BLACKLISTED_DOMAINS = {
    # "exemplo-spam.com", "phishing.net" # Exemplo: domínios de spam/phishing
}

# Domínios de e-mails temporários/descartáveis (podem vir de uma lista externa ou ser mantidos aqui)
TEMPORARY_DOMAINS = {
    "mailinator.com", "tempmail.com", "yopmail.com", "guerrillamail.com", "10minutemail.com", # Exemplos
    # Adicione outros domínios de e-mails temporários aqui
}

WHITELISTED_DOMAINS = {
    # "suaempresa.com.br", "parceiro.com" # Exemplo: apenas e-mails destes domínios são permitidos
}

class EmailValidator(BaseValidator): # Herda de BaseValidator
    # Códigos de Regra específicos para validação de e-mail (Padronização RN_EMAILxxx)
    # Definidos como atributos de CLASSE para acesso via self.RN_EMAIL_xxx
    RN_EMAIL_VALID_SYNTAX = "RN_EMAIL001" # Sintaxe básica válida (regex fallback)
    RN_EMAIL_VALID_DOMAIN = "RN_EMAIL002"  # Domínio válido (MX record, etc. - via email_validator)
    RN_EMAIL_INVALID_FORMAT = "RN_EMAIL003" # Formato geral inválido (não passa regex ou lib)
    RN_EMAIL_TEMPORARY_DOMAIN = "RN_EMAIL004" # Domínio de e-mail temporário/descartável
    RN_EMAIL_BLACK_LISTED_DOMAIN = "RN_EMAIL005" # Domínio na lista negra
    RN_EMAIL_WHITELISTED_DOMAIN = "RN_EMAIL006" # Domínio não está na lista branca (e a whitelist está ativa e é restritiva)
    RN_EMAIL_EMPTY_OR_INVALID_INPUT = "RN_EMAIL007" # Input vazio ou tipo inválido

    """
    Validador de endereços de e-mail com regras e fallback.
    Utiliza a biblioteca 'email_validator' para validação robusta
    e inclui regras em memória (regex, blacklists) para cenários específicos
    ou quando a biblioteca principal não está disponível.
    """

    def __init__(self):
        super().__init__(origin_name="email_validator") # Inicializa o BaseValidator
        logger.info("EmailValidator inicializado.")

    async def validate(self, data: Any, check_temporary_domains: bool = True, **kwargs) -> Dict[str, Any]: # MÉTODO PADRONIZADO 'validate'
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
                                - "input_data_cleaned": O e-mail normalizado.
                                - "is_disposable": True se for um domínio de e-mail temporário/descartável.
                                - "is_blacklisted": True se o domínio estiver na lista negra.
                                - "is_whitelisted": True/False/None (se whitelist aplicada).
                                - "validation_details": Dicionário para detalhes adicionais da validação.
                            - "business_rule_applied" (dict): Detalhes da regra de negócio aplicada.
        """
        email = data # 'data' é o endereço de email
        
        initial_details = {
            "input_original": email,
            "is_disposable": False,
            "is_blacklisted": False,
            "is_whitelisted": None, # Inicialmente None, será True/False se WHITELISTED_DOMAINS não for vazio
            "validation_details": {}
        }
        
        # 1. Normalização e Verificação de Input Vazio
        if not isinstance(email, str) or not email.strip():
            return self._format_result(
                is_valid=False,
                dado_normalizado=None,
                mensagem="Endereço de e-mail vazio ou tipo inválido.",
                details=initial_details,
                business_rule_applied={"code": self.RN_EMAIL_EMPTY_OR_INVALID_INPUT, "type": "Email - Validação Primária", "name": "Input de Email Vazio ou Inválido"}
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
                business_rule_applied={"code": self.RN_EMAIL_INVALID_FORMAT, "type": "Email - Validação Primária", "name": "Formato Básico de Email Inválido"}
            )

        # 2. Validação da Sintaxe e Domínio (com fallback)
        is_syntax_valid = False
        is_domain_resolvable = False # Renomeado para mais clareza no contexto de 'email_validator'
        final_message = ""
        final_rule_code = self.RN_EMAIL_INVALID_FORMAT # Default para falha

        if EMAIL_VALIDATOR_AVAILABLE:
            try:
                # check_deliverability=True verifica registros MX e tentativa de conexão SMTP.
                # Pode ser mais lento, mas torna a validação mais robusta.
                valid_email_info = validate_email(normalized_email, check_deliverability=True)
                is_syntax_valid = True
                is_domain_resolvable = True
                final_message = "E-mail válido e domínio resolvível (verificado por biblioteca 'email_validator')."
                final_rule_code = self.RN_EMAIL_VALID_DOMAIN # Mais específico que apenas sintaxe
                initial_details["validation_details"]["email_validator_info"] = valid_email_info.as_dict()
                initial_details["validation_details"]["is_syntax_valid"] = True
                initial_details["validation_details"]["domain_resolves"] = True

            except EmailNotValidError as e:
                final_message = f"E-mail inválido: {e}"
                initial_details["validation_details"]["email_validator_error"] = str(e)
                # Verifica se o erro está relacionado ao domínio/DNS para melhor granularidade
                if "domain" in str(e).lower() or "dns" in str(e).lower():
                    is_domain_resolvable = False
                    initial_details["validation_details"]["domain_resolves"] = False
                    final_rule_code = self.RN_EMAIL_INVALID_FORMAT # Pode ser também RN_EMAIL_INVALID_DOMAIN se a regra existisse isolada
                else:
                    is_syntax_valid = False
                    initial_details["validation_details"]["is_syntax_valid"] = False
                    final_rule_code = self.RN_EMAIL_INVALID_FORMAT
                
                # Se 'email_validator' explicitamente diz que é inválido, retorna imediatamente
                return self._format_result(
                    is_valid=False,
                    dado_normalizado=normalized_email,
                    mensagem=final_message,
                    details=initial_details,
                    business_rule_applied={"code": final_rule_code, "type": "Email - Validação Primária", "name": "Falha na Validação Principal de Email"}
                )
            except Exception as e: # Captura outros erros inesperados da biblioteca
                logger.error(f"Erro inesperado com 'email_validator' para '{normalized_email}': {e}", exc_info=True)
                final_message = f"Erro interno na validação de e-mail: {e}. Revertendo para validação básica."
                initial_details["validation_details"]["unexpected_error"] = str(e)
                # Fallback para regex se a biblioteca falhar inesperadamente
                is_syntax_valid = re.match(r"[^@]+@[^@]+\.[^@]+", normalized_email) is not None
                is_domain_resolvable = True # Assume válido para as próximas checagens, já que a lib falhou
                final_rule_code = self.RN_EMAIL_INVALID_FORMAT # Ainda é um problema de formato, mas devido a erro interno

        # Fallback para regex básica se 'email_validator' não estiver disponível ou falhou inesperadamente
        if not EMAIL_VALIDATOR_AVAILABLE or not is_syntax_valid: # Usa is_syntax_valid do bloco anterior
            is_syntax_valid = re.match(r"[^@]+@[^@]+\.[^@]+", normalized_email) is not None
            initial_details["validation_details"]["is_syntax_valid_regex"] = is_syntax_valid
            if not is_syntax_valid:
                return self._format_result(
                    is_valid=False,
                    dado_normalizado=normalized_email,
                    mensagem="Formato de e-mail inválido (regex).",
                    details=initial_details,
                    business_rule_applied={"code": self.RN_EMAIL_INVALID_FORMAT, "type": "Email - Validação Primária", "name": "Formato de Email Inválido (Regex Fallback)"}
                )
            # Se regex passou, mas email_validator teve problemas
            final_message = "E-mail válido (verificação básica por regex), prosseguindo com filtros de domínio."
            final_rule_code = self.RN_EMAIL_VALID_SYNTAX # Menos específico que RN_EMAIL_VALID_DOMAIN

        # 3. Verificação de Domínios Temporários/Descartáveis e Blacklist
        # Verifica se o domínio está na lista de temporários
        if check_temporary_domains and domain in TEMPORARY_DOMAINS:
            initial_details["is_disposable"] = True
            return self._format_result(
                is_valid=False,
                dado_normalizado=normalized_email,
                mensagem="E-mail inválido: domínio de e-mail temporário/descartável.",
                details=initial_details,
                business_rule_applied={"code": self.RN_EMAIL_TEMPORARY_DOMAIN, "type": "Email - Validação Primária", "name": "Domínio de Email Temporário/Descartável"}
            )
        # Verifica se o domínio está na lista negra (separado dos temporários)
        if domain in BLACKLISTED_DOMAINS:
            initial_details["is_blacklisted"] = True
            return self._format_result(
                is_valid=False,
                dado_normalizado=normalized_email,
                mensagem="E-mail inválido: domínio na lista negra.",
                details=initial_details,
                business_rule_applied={"code": self.RN_EMAIL_BLACK_LISTED_DOMAIN, "type": "Email - Validação Primária", "name": "Domínio de Email na Lista Negra"}
            )
        
        # 4. Verificação de Whitelist (se houver e for restritiva)
        if WHITELISTED_DOMAINS: # Só aplica se a whitelist não estiver vazia
            initial_details["is_whitelisted"] = domain in WHITELISTED_DOMAINS
            if not initial_details["is_whitelisted"]: # Se não está na whitelist
                return self._format_result(
                    is_valid=False,
                    dado_normalizado=normalized_email,
                    mensagem="E-mail inválido: domínio não está na lista branca permitida.",
                    details=initial_details,
                    business_rule_applied={"code": self.RN_EMAIL_WHITELISTED_DOMAIN, "type": "Email - Validação Primária", "name": "Domínio de Email Não Whitelisted"}
                )
        
        # Se chegou até aqui, o e-mail passou por todas as validações e filtros
        return self._format_result(
            is_valid=True,
            dado_normalizado=normalized_email,
            mensagem=final_message, # Usa a mensagem definida durante o processo de validação principal
            details=initial_details,
            business_rule_applied={"code": final_rule_code, "type": "Email - Validação Primária", "name": "Email Validado com Sucesso"}
        )
    
    def _normalize_email(self, email: str) -> str:
        """Normaliza o endereço de e-mail para minúsculas e remove espaços em branco extras."""
        return email.strip().lower()

    def _format_result(self, is_valid: bool, dado_normalizado: Optional[str], mensagem: str,
                         details: Dict[str, Any], business_rule_applied: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata o resultado da validação em um dicionário padronizado.

        Args:
            is_valid (bool): Indica se a validação foi bem-sucedida.
            dado_normalizado (Optional[str]): O e-mail normalizado.
            mensagem (str): Mensagem de status da validação.
            details (Dict[str, Any]): Detalhes específicos da validação.
            business_rule_applied (Dict[str, Any]): Regra de negócio aplicada.

        Returns:
            Dict[str, Any]: Resultado formatado da validação.
        """
        return {
            "is_valid": is_valid,
            "dado_normalizado": dado_normalizado,
            "mensagem": mensagem,
            "origem_validacao": self.origin_name,
            "details": details,
            "business_rule_applied": business_rule_applied
        }
