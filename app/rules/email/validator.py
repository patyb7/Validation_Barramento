# app/rules/email/validator.py

import re
from typing import Dict, Any

# Códigos de Regra específicos para validação de e-mail
RNE_VALID_SYNTAX = "RNE001"        # Sintaxe básica válida
RNE_VALID_DOMAIN = "RNE002"        # Domínio válido (MX record, etc.)
RNE_INVALID_FORMAT = "RNE003"      # Formato geral inválido (regex ou lib)
RNE_TEMPORARY_DOMAIN = "RNE004"    # Domínio de e-mail temporário/descartável
RNE_BLACK_LISTED_DOMAIN = "RNE005" # Domínio na lista negra
RNE_WHITELISTED_DOMAIN = "RNE006"  # Domínio na lista branca (exigindo)

# --- Configuração e carregamento da biblioteca email_validator ---
EMAIL_VALIDATOR_AVAILABLE = True
try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:
    EMAIL_VALIDATOR_AVAILABLE = False
    print("WARNING: A biblioteca 'email_validator' não está instalada. A validação de e-mail será básica (apenas regex).")
except Exception as e:
    EMAIL_VALIDATOR_AVAILABLE = False
    print(f"ERROR: Erro inesperado ao carregar ou configurar email_validator: {e}. Desativando.")

# --- Regras em Memória (Fallback e Heurísticas) ---
# Você pode expandir estas listas conforme necessário
BLACKLISTED_DOMAINS = {
    "mailinator.com", "tempmail.com", "yopmail.com", # Exemplos de domínios de e-mails temporários
    # Adicione outros domínios conhecidos por spam ou fraude aqui
}

WHITELISTED_DOMAINS = {
    # "suaempresa.com.br", "parceiro.com" # Exemplo: apenas e-mails destes domínios são permitidos
}

class EmailValidator:
    """
    Validador de endereços de e-mail com regras e fallback.
    Utiliza a biblioteca 'email_validator' para validação robusta
    e inclui regras em memória (regex, blacklists) para cenários específicos
    ou quando a biblioteca principal não está disponível.
    """

    def __init__(self):
        pass # Nenhuma inicialização específica necessária

    def validate(self, email: str, check_temporary_domains: bool = True) -> Dict[str, Any]:
        """
        Valida um endereço de e-mail aplicando uma sequência de regras.

        Args:
            email: O endereço de e-mail a ser validado.
            check_temporary_domains: Se deve verificar domínios de e-mail temporários.

        Returns:
            Um dicionário com os detalhes da validação:
            - "input_data_original": O e-mail original submetido.
            - "input_data_cleaned": O e-mail normalizado (minúsculas, sem espaços).
            - "valido": True se o e-mail é considerado válido, False caso contrário.
            - "mensagem": Mensagem explicativa do resultado da validação.
            - "origem_validacao": Fonte principal da validação (e.g., "email_validator", "fallback_regex").
            - "regra_codigo": O código da regra que determinou o resultado final.
            - "is_disposable": True se for um domínio de e-mail temporário.
            - "is_blacklisted": True se o domínio estiver na lista negra.
            - "validation_details": Dicionário para detalhes adicionais da validação.
        """
        validation_result = {
            "input_data_original": email,
            "input_data_cleaned": "",
            "valido": False,
            "mensagem": "Falha na validação inicial do e-mail.",
            "origem_validacao": "servico_validador_email",
            "regra_codigo": RNE_INVALID_FORMAT,
            "is_disposable": False,
            "is_blacklisted": False,
            "validation_details": {}
        }

        # 1. Normalização do e-mail
        normalized_email = self._normalize_email(email)
        validation_result["input_data_cleaned"] = normalized_email

        if not normalized_email:
            validation_result["mensagem"] = "Endereço de e-mail vazio ou não contém caracteres válidos."
            return validation_result

        # Extrai o domínio para verificações posteriores
        domain_match = re.search(r'@([^@]+)$', normalized_email)
        domain = domain_match.group(1).lower() if domain_match else ""

        # 2. Verifica Whitelisted Domains (se aplicável, com prioridade máxima)
        # Se você tiver uma whitelist e ela for estrita (só permite emails da whitelist)
        if WHITELISTED_DOMAINS and domain not in WHITELISTED_DOMAINS:
            validation_result["mensagem"] = f"Domínio '{domain}' não está na lista branca permitida."
            validation_result["regra_codigo"] = RNE_WHITELISTED_DOMAIN
            return validation_result
        
        # 3. Verifica Blacklisted/Temporary Domains (prioridade alta)
        if domain in BLACKLISTED_DOMAINS:
            validation_result["is_blacklisted"] = True
            validation_result["mensagem"] = f"Domínio '{domain}' está na lista negra de e-mails."
            validation_result["regra_codigo"] = RNE_BLACK_LISTED_DOMAIN
            validation_result["valido"] = False # Um e-mail de um domínio blacklistado é inválido
            return validation_result

        # Tenta verificar se é um domínio temporário usando a lib email_validator
        if EMAIL_VALIDATOR_AVAILABLE and check_temporary_domains:
            try:
                # O email_validator pode ter uma lista interna de domínios descartáveis
                # ou você pode usar um serviço externo se a lib não tiver.
                # Para simplificar, confiamos no check_temporary_domains se for implementado
                # na validação principal ou na nossa blacklist.
                # Por padrão, ele verifica syntax e dns, mas não temporários explicitamente na lib.
                pass # A lógica de `is_disposable` é mais comumente externa ou via blacklist manual
            except Exception as e:
                print(f"WARNING: Erro ao verificar domínio temporário: {e}")


        # 4. Validação Principal com email_validator (se disponível)
        if EMAIL_VALIDATOR_AVAILABLE:
            validation_result["origem_validacao"] = "email_validator"
            try:
                # `check_deliverability` é um parâmetro importante, mas pode ser lento
                # e requer acesso DNS. Para este exemplo, vamos desativar por padrão.
                # email_info = validate_email(normalized_email, check_deliverability=False)
                email_info = validate_email(normalized_email) 
                
                # Se passou pela validação, é considerado válido sintaticamente e de domínio
                validation_result["valido"] = True
                validation_result["mensagem"] = "Endereço de e-mail válido (via email_validator)."
                validation_result["regra_codigo"] = RNE_VALID_SYNTAX
                validation_result["validation_details"]["email_info"] = email_info.as_dict() # Detalhes da lib

                # Se o domínio não é blacklistado e passou na validação da lib, é válido.
                return validation_result

            except EmailNotValidError as e:
                validation_result["mensagem"] = f"Endereço de e-mail inválido (via email_validator): {e}"
                validation_result["valido"] = False
                validation_result["regra_codigo"] = RNE_INVALID_FORMAT
                # Continua para o fallback para uma segunda chance ou para registrar a falha
            except Exception as e:
                validation_result["mensagem"] = f"Erro inesperado durante validação com email_validator: {e}. Tentando fallback."
                validation_result["valido"] = False
                validation_result["regra_codigo"] = RNE_INVALID_FORMAT
                # Continua para o fallback

        # 5. Validação de Fallback (Regex)
        # Esta camada só é alcançada se email_validator não está disponível ou falhou.
        validation_result["origem_validacao"] = "fallback_regex"

        # Regex para validação de formato básico de e-mail
        # Este regex é simplificado e não cobre todas as nuances (RFCs), mas é um bom fallback.
        # Ele verifica a presença de @ e pelo menos um ponto após o @ no domínio.
        email_regex = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

        if email_regex.fullmatch(normalized_email):
            validation_result["valido"] = True
            validation_result["mensagem"] = "Endereço de e-mail válido (via fallback regex)."
            validation_result["regra_codigo"] = RNE_VALID_SYNTAX
        else:
            validation_result["valido"] = False
            validation_result["mensagem"] = "Endereço de e-mail com formato inválido (via fallback regex)."
            validation_result["regra_codigo"] = RNE_INVALID_FORMAT
            
        return validation_result

    def _normalize_email(self, email: str) -> str:
        """
        Normaliza o endereço de e-mail: remove espaços em branco e converte para minúsculas.
        """
        if not email:
            return ""
        return email.strip().lower()