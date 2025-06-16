#app/rules/decision_rules.py
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Importações internas (ajuste conforme a sua estrutura de pastas se necessário)
from ..database.repositories import ValidationRecordRepository
from ..models.validation_record import ValidationRecord

logger = logging.getLogger(__name__)

class DecisionRules:
    """
    Aplica regras de decisão de negócio e ações pós-validação de forma flexível
    para diversos sistemas/produtos (Seguros, Consórcio, Crédito, etc.).
    Estas regras operam sobre o resultado da validação primária e metadados da aplicação,
    definindo o 'regra_codigo' (código da regra de negócio/ação) e enriquecendo 'validation_details'.
    """

    # Definição centralizada das REGRAS DE NEGÓCIO com seus metadados
    BUSINESS_RULES = {
        # Regras de Validação Primária (podem ser usadas por apps específicos)
        "VAL_PHN_BASIC": {
            "type": "Validação de Telefone",
            "name": "Validação Básica de Telefone",
            "description": "Verifica se o telefone é válido no formato geral (número, código de país).",
            "rule_definition": "Telefone válido de acordo com o validador base.",
            "result_status": "Validação OK",
            "fail_status": "Validação Falha",
            "impact": "Determina a validade fundamental do telefone."
        },
        "VAL_CEP_BASIC": {
            "type": "Validação de CEP",
            "name": "Validação Básica de CEP",
            "description": "Verifica se o CEP é um formato válido no Brasil.",
            "rule_definition": "CEP válido de acordo com o validador base.",
            "result_status": "Validação OK",
            "fail_status": "Validação Falha",
            "impact": "Determina a validade fundamental do CEP."
        },

        # Regras de Negócio de Telefone (contexto-sensíveis)
        "RN_TEL_BR_MOBILE_APP": {
            "type": "Telefone - Celular BR Específico por App",
            "name": "Telefone Celular BR para Apps Específicos",
            "description": "Verifica se o telefone é um celular BR válido (+55 DDD 9NNNN-NNNN), não sequencial/repetido, para aplicações que exigem alta conformidade (e.g., Seguros, Consórcio, Crédito).",
            "rule_definition": "Telefone válido (celular BR, não sequencial/repetido) E a aplicação é de um dos sistemas listados (ex: Seguros, Consórcio, Crédito).",
            "result_status": "Aprovado pela Regra de Negócio",
            "fail_status": "Reprovado pela Regra de Negócio",
            "impact": "Liberação para cadastro/processamento em sistemas de alta conformidade."
        },
        "RN_TEL_INVALID_APP": {
            "type": "Telefone - Inválido por App",
            "name": "Telefone Não Conforme para Apps Específicos",
            "description": "Telefone não atende aos critérios da regra RN_TEL_BR_MOBILE_APP para aplicações específicas.",
            "rule_definition": "Telefone inválido ou não segue o padrão celular BR (DDD 9 dígitos, não sequencial/repetido) para aplicações específicas.",
            "result_status": "Não Aprovado pela Regra de Negócio",
            "fail_status": "Não Aprovado pela Regra de Negócio",
            "impact": "Bloqueio ou alerta em processos de sistemas de alta conformidade."
        },

        # Regras de Negócio de CEP (contexto-sensíveis)
        "RN_CEP_PJ_CLIENT": {
            "type": "CEP - Cliente PJ Específico",
            "name": "CEP Válido para Clientes PJ",
            "description": "Verifica se o CEP é válido E o cliente é Pessoa Jurídica, para qualquer aplicação que lide com dados PJ.",
            "rule_definition": "CEP válido (não sequencial/repetido) E 'client_identifier' indica PJ (e.g., começa com 'PJ').",
            "result_status": "Aprovado pela Regra de Negócio",
            "fail_status": "Reprovado pela Regra de Negócio",
            "impact": "Liberação para cadastro de endereço de Pessoa Jurídica."
        },
        "RN_CEP_INVALID_PJ": {
            "type": "CEP - Inválido para Cliente PJ",
            "name": "CEP Não Conforme para Clientes PJ",
            "description": "CEP não atende aos critérios da regra RN_CEP_PJ_CLIENT para clientes PJ.",
            "rule_definition": "CEP inválido ou cliente não é PJ (ou não começa com 'PJ').",
            "result_status": "Não Aprovado pela Regra de Negócio",
            "fail_status": "Não Aprovado pela Regra de Negócio",
            "impact": "Bloqueio ou alerta no cadastro de endereço PJ."
        },

        # Regras de Ação (podem ou não ser baseadas em validação ou negócio)
        "RN_A_001": {
            "type": "Ação",
            "name": "Soft Delete de Registros Inválidos",
            "description": "Marca registros de validação inválidos para soft delete se a aplicação chamadora tiver a permissão.",
            "rule_definition": "Se record.is_valido for False E app_info.can_delete_invalid for True, então soft delete.",
            "result_status": "Ação Executada",
            "fail_status": "Ação Não Executada",
            "impact": "Limpeza de dados de validação inválidos."
        },
        "RN_A_002": {
            "type": "Ação",
            "name": "Verificação de Duplicidade de Dados Válidos",
            "description": "Verifica se um dado válido normalizado já existe no histórico de validações.",
            "rule_definition": "Se record.is_valido for True E app_info.can_check_duplicates for True E record.dado_normalizado não for nulo, então busca duplicatas no BD.",
            "result_status": "Duplicidade Verificada",
            "fail_status": "Duplicidade Não Verificada",
            "impact": "Alerta sobre dados repetidos."
        },
        "RN_NEGOCIO_PADRAO": {
            "type": "Geral",
            "name": "Nenhuma Regra de Negócio Específica Aplicada",
            "description": "Nenhum dos critérios para as regras de negócio específicas foram atendidos.",
            "rule_definition": "Verificar se as condições de outras regras de negócio se aplicam.",
            "result_status": "N/A",
            "fail_status": "N/A",
            "impact": "Nenhum impacto direto pela regra de negócio."
        }
    }

    # Aplicações que exigem validação de telefone BR de celular e não sequencial/repetido
    APPS_REQUIRING_STRICT_PHONE = ["Seguros App", "Consorcio Web", "Credito Direto"]
    
    def __init__(self, repo: ValidationRecordRepository):
        self.repo: ValidationRecordRepository = repo
        logger.info("DecisionRules inicializado com o catálogo de regras de negócio generalizado.")

    def apply_post_validation_actions(self, record: ValidationRecord, app_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplica um conjunto de regras de decisão de negócio a um registro de validação
        recém-criado, com base nas permissões e contexto da aplicação chamadora.
        Modifica o 'record' diretamente (in-place) para atualizar 'regra_codigo' e 'validation_details'.

        Args:
            record: O objeto ValidationRecord recém-criado/salvo no banco de dados.
            app_info: Dicionário contendo os metadados da aplicação (API Key).
                      Esperado campos como 'app_name', 'can_delete_invalid', 'can_check_duplicates'.

        Returns:
            Um dicionário com um resumo das ações e regras de negócio aplicadas.
        """
        app_name = app_info.get("app_name", "Aplicação Desconhecida")
        actions_summary = {}
        
        logger.info(f"Iniciando aplicação de regras de decisão para registro ID: {record.id}, App: '{app_name}'")

        # Priorize as regras de negócio específicas (que podem definir o 'regra_codigo' principal)
        self._apply_specific_business_rules(record, app_name, actions_summary)

        # Em seguida, aplique as regras de ação (que geralmente não alteram o 'regra_codigo' principal,
        # mas realizam ações no banco de dados ou adicionam informações aos detalhes).
        self._rule_soft_delete_invalid_records(record, app_info, actions_summary)
        self._rule_check_duplicates(record, app_info, actions_summary)

        logger.info(f"Regras de decisão aplicadas para registro ID: {record.id}. Sumário: {actions_summary}")
        return actions_summary

    def _apply_specific_business_rules(self, record: ValidationRecord, app_name: str, actions_summary: Dict[str, Any]):
        """
        Aplica regras de negócio que podem definir o 'regra_codigo' principal
        e adicionar detalhes relevantes ao 'validation_details' do registro.
        """
        record.validation_details.setdefault("business_rule_applied", {})
        
        if record.tipo_validacao == "telefone":
            self._apply_phone_business_rules(record, app_name, actions_summary)
        elif record.tipo_validacao == "cep":
            self._apply_cep_business_rules(record, app_name, actions_summary)
        # Adicione mais 'elif' para outros tipos de validação aqui

        # Se nenhuma regra de negócio específica foi aplicada pelo tipo de validação
        # ou se as regras específicas não definiram um 'regra_codigo', use a padrão.
        if record.regra_negocio_codigo is None:
            self._set_default_business_rule(record, actions_summary)

    def _set_default_business_rule(self, record: ValidationRecord, actions_summary: Dict[str, Any]):
        """Define a regra de negócio padrão se nenhuma específica for aplicada."""
        rule_code = "RN_NEGOCIO_PADRAO"
        rule_metadata = self.BUSINESS_RULES.get(rule_code)
        if rule_metadata:
            record.regra_negocio_codigo = rule_code # Adicionado para consistência com o modelo
            record.regra_negocio_descricao = rule_metadata["description"] # <--- Adicionado
            # Adiciona os metadados da regra de negócio ao registro
            record.regra_negocio_tipo = rule_metadata["type"] # <--- Adicionado
            record.regra_negocio_parametros = {} # <--- Adicionado (se não houver parâmetros específicos)

            record.validation_details["business_rule_applied"] = {
                "code": rule_code,
                "type": rule_metadata["type"],
                "name": rule_metadata["name"],
                "description": rule_metadata["description"],
                "rule_definition": rule_metadata["rule_definition"],
                "result": rule_metadata["result_status"],
                "impact": rule_metadata["impact"]
            }
            actions_summary["specific_business_rule_status"] = "NONE_APPLIED"
            logger.debug(f"[Regra Negócio] Regra padrão '{rule_code}' aplicada para registro ID {record.id}.")

    def _apply_phone_business_rules(self, record: ValidationRecord, app_name: str, actions_summary: Dict[str, Any]):
        """
        Aplica regras de negócio específicas para o tipo 'phone', considerando diferentes apps.
        """
        # Condições comuns para muitas regras de telefone
        is_valid_by_validator = record.is_valido
        is_brazilian_mobile = False
        # VAL_PHN013 no validador indica que é sequencial/repetido
        is_not_sequential_or_repeated = (record.validation_details.get("validation_code") != "VAL_PHN013")

        # Verifica se é um celular brasileiro (se phonenumbers o identificou ou via fallback)
        if record.validation_details.get("type_detected") in ["Celular", "Celular BR"]:
            is_brazilian_mobile = True

        # RN_TEL_BR_MOBILE_APP: Telefone Celular BR para Apps Específicos (Seguros, Consórcio, Crédito)
        if is_valid_by_validator and is_brazilian_mobile and is_not_sequential_or_repeated and app_name in self.APPS_REQUIRING_STRICT_PHONE:
            rule_code = "RN_TEL_BR_MOBILE_APP"
            rule_metadata = self.BUSINESS_RULES.get(rule_code)
            if rule_metadata:
                record.regra_negocio_codigo = rule_code # <--- Adicionado
                record.regra_negocio_descricao = rule_metadata["description"] # <--- Adicionado
                record.regra_negocio_tipo = rule_metadata["type"] # <--- Adicionado
                record.regra_negocio_parametros = {} # <--- Adicionado

                record.validation_details["business_rule_applied"] = {
                    "code": rule_code,
                    "type": rule_metadata["type"],
                    "name": rule_metadata["name"],
                    "description": rule_metadata["description"],
                    "rule_definition": rule_metadata["rule_definition"],
                    "result": rule_metadata["result_status"],
                    "impact": rule_metadata["impact"]
                }
                actions_summary[f"{rule_code}_status"] = "APPLIED_SUCCESS"
                actions_summary[f"{rule_code}_message"] = f"Regra {rule_code} aplicada: Telefone aprovado para {app_name}."
                logger.info(f"[Regra Negócio] {rule_code} aplicada para telefone {record.dado_original} do app {app_name}.")
            
        # RN_TEL_INVALID_APP: Telefone Não Conforme para Apps Específicos
        # Aplica se a validação primária falhou E a aplicação é uma das que exige conformidade
        elif not is_valid_by_validator and app_name in self.APPS_REQUIRING_STRICT_PHONE: 
            rule_code = "RN_TEL_INVALID_APP"
            rule_metadata = self.BUSINESS_RULES.get(rule_code)
            if rule_metadata:
                
                record.regra_negocio_codigo = rule_code # <--- Adicionado
                record.regra_negocio_descricao = rule_metadata["description"] # <--- Adicionado
                record.regra_negocio_tipo = rule_metadata["type"] # <--- Adicionado
                record.regra_negocio_parametros = {} # <--- Adicionado

                record.validation_details["business_rule_applied"] = {
                    "code": rule_code,
                    "type": rule_metadata["type"],
                    "name": rule_metadata["name"],
                    "description": rule_metadata["description"],
                    "rule_definition": rule_metadata["rule_definition"],
                    "result": rule_metadata["fail_status"],
                    "impact": rule_metadata["impact"]
                }
                actions_summary[f"{rule_code}_status"] = "APPLIED_FAILURE"
                actions_summary[f"{rule_code}_message"] = f"Regra {rule_code} aplicada: Telefone reprovado para {app_name}."
                logger.info(f"[Regra Negócio] {rule_code} aplicada para telefone {record.dado_original} do app {app_name}.")
            
        # Se nenhuma das regras específicas acima foi aplicada, a regra padrão será definida no método chamador.

    def _apply_cep_business_rules(self, record: ValidationRecord, app_name: str, actions_summary: Dict[str, Any]):
        """
        Aplica regras de negócio específicas para o tipo 'cep', considerando diferentes apps/clientes.
        """
        # Condições comuns para muitas regras de CEP
        is_valid_by_validator = record.is_valido
        # Verifica se o cliente é Pessoa Jurídica (PJ) baseado no identificador do cliente
        # Exemplo: Se o identificador do cliente começa com "PJ", consideramos que é PJ
        is_client_pj = record.client_identifier and record.client_identifier.upper().startswith("PJ")
        # VAL_CEP004 no validador indica que é sequencial/repetido
        is_not_sequential_or_repeated_cep = (record.validation_details.get("validation_code") != "VAL_CEP004")

        # RN_CEP_PJ_CLIENT: CEP Válido para Clientes PJ
        if is_valid_by_validator and is_client_pj and is_not_sequential_or_repeated_cep:
            rule_code = "RN_CEP_PJ_CLIENT"
            rule_metadata = self.BUSINESS_RULES.get(rule_code)
            if rule_metadata:
                
                record.regra_negocio_codigo = rule_code # <--- Adicionado
                record.regra_negocio_descricao = rule_metadata["description"] # <--- Adicionado
                record.regra_negocio_tipo = rule_metadata["type"] # <--- Adicionado
                record.regra_negocio_parametros = {} # <--- Adicionado

                record.validation_details["business_rule_applied"] = {
                    "code": rule_code,
                    "type": rule_metadata["type"],
                    "name": rule_metadata["name"],
                    "description": rule_metadata["description"],
                    "rule_definition": rule_metadata["rule_definition"],
                    "result": rule_metadata["result_status"],
                    "impact": rule_metadata["impact"]
                }
                actions_summary[f"{rule_code}_status"] = "APPLIED_SUCCESS"
                actions_summary[f"{rule_code}_message"] = f"Regra {rule_code} aplicada: CEP aprovado para Cliente PJ."
                logger.info(f"[Regra Negócio] {rule_code} aplicada para CEP {record.dado_original} do cliente PJ.")
            
        # RN_CEP_INVALID_PJ: CEP Não Conforme para Clientes PJ
        elif not is_valid_by_validator and is_client_pj: 
            rule_code = "RN_CEP_INVALID_PJ"
            rule_metadata = self.BUSINESS_RULES.get(rule_code)
            if rule_metadata:
                
                record.regra_negocio_codigo = rule_code # <--- Adicionado
                record.regra_negocio_descricao = rule_metadata["description"] # <--- Adicionado
                record.regra_negocio_tipo = rule_metadata["type"] # <--- Adicionado
                record.regra_negocio_parametros = {} # <--- Adicionado

                record.validation_details["business_rule_applied"] = {
                    "code": rule_code,
                    "type": rule_metadata["type"],
                    "name": rule_metadata["name"],
                    "description": rule_metadata["description"],
                    "rule_definition": rule_metadata["rule_definition"],
                    "result": rule_metadata["fail_status"],
                    "impact": rule_metadata["impact"]
                }
                actions_summary[f"{rule_code}_status"] = "APPLIED_FAILURE"
                actions_summary[f"{rule_code}_message"] = f"Regra {rule_code} aplicada: CEP reprovado para Cliente PJ."
                logger.info(f"[Regra Negócio] {rule_code} aplicada para CEP {record.dado_original} do cliente PJ.")
            
        # Se nenhuma das regras específicas acima foi aplicada, a regra padrão será definida no método chamador.

    def _rule_soft_delete_invalid_records(self, record: ValidationRecord, app_info: Dict[str, Any], actions_summary: Dict[str, Any]):
        """
        Regra de Ação: Se o registro é inválido e a aplicação tem a permissão 'can_delete_invalid',
        marca o registro para soft delete no banco de dados.
        Código da Regra de Ação: RN_A_001
        """
        rule_code = "RN_A_001"
        rule_metadata = self.BUSINESS_RULES.get(rule_code)

        if not record.is_valido and app_info.get("can_delete_invalid", False):
            logger.info(f"Tentando soft delete para registro ID {record.id} (inválido). App '{app_info.get('app_name')}' tem permissão.")
            try:
                # Importante: record.id já deve estar definido aqui, pois a persistência inicial ocorre antes.
                success = self.repo.soft_delete_record(record.id) # Alterado de soft_delete_record_by_id para soft_delete_record
                if success:
                    record.is_deleted = True
                    record.deleted_at = datetime.now() 
                    actions_summary["soft_delete_action"] = {
                        "code": rule_code,
                        "status": rule_metadata["result_status"] if rule_metadata else "Executed",
                        "message": "Registro inválido foi marcado para soft delete com sucesso."
                    }
                    logger.info(f"[Ação] Registro ID {record.id} (Inválido) marcado para soft delete pela aplicação '{app_info.get('app_name')}'.")
                else:
                    actions_summary["soft_delete_action"] = {
                        "code": rule_code,
                        "status": rule_metadata["fail_status"] if rule_metadata else "Failed",
                        "message": "Falha ao marcar registro inválido para soft delete (repositório retornou falha, ou já estava deletado/não encontrado)."
                    }
                    logger.warning(f"[Ação] Falha ao marcar registro ID {record.id} para soft delete. App: '{app_info.get('app_name')}'.")
            except Exception as e:
                actions_summary["soft_delete_action"] = {
                    "code": rule_code,
                    "status": rule_metadata["fail_status"] if rule_metadata else "Error",
                    "message": f"Erro inesperado ao tentar soft delete de registro inválido: {e}"
                }
                logger.error(f"[Ação] Erro ao tentar soft delete para registro ID {record.id}: {e}", exc_info=True)
        else:
            actions_summary["soft_delete_action"] = {
                "code": rule_code,
                "status": "Not Applicable",
                "message": "Regra de soft delete de inválidos não aplicada (registro válido ou sem permissão)."
            }
            logger.debug(f"Soft delete de inválidos não aplicado para registro ID {record.id}. Válido: {record.is_valido}, Permissão: {app_info.get('can_delete_invalid', False)}.")


    def _rule_check_duplicates(self, record: ValidationRecord, app_info: Dict[str, Any], actions_summary: Dict[str, Any]):
        """
        Regra de Ação: Se o registro é válido e a aplicação tem a permissão 'can_check_duplicates',
        verifica se já existe um registro similar no banco de dados.
        Código da Regra de A002.
        """
        rule_code = "RN_A_002"
        rule_metadata = self.BUSINESS_RULES.get(rule_code)

        if record.is_valido and app_info.get("can_check_duplicates", False) and record.dado_normalizado:
            logger.info(f"Tentando verificar duplicidade para registro ID {record.id}. App '{app_info.get('app_name')}' tem permissão.")
            try:
                # Exclui o próprio record.id da busca para não se considerar um duplicado
                duplicate_record_found: Optional[ValidationRecord] = self.repo.find_duplicate_record(
                    dado_normalizado=record.dado_normalizado,
                    tipo_validacao=record.tipo_validacao,
                    exclude_record_id=record.id # Garante que não encontra a si mesmo
                )

                if duplicate_record_found:
                    actions_summary["duplicate_check_action"] = {
                        "code": rule_code,
                        "status": rule_metadata["result_status"] if rule_metadata else "Executed",
                        "message": (
                            f"Dado '{record.dado_normalizado}' (Tipo: {record.tipo_validacao}) é um DUPLICADO. "
                            f"Registro existente ID: {duplicate_record_found.id}."
                        ),
                        "is_duplicate": True,
                        "duplicate_id": duplicate_record_found.id
                    }
                    logger.warning(
                        f"[Ação] Aplicação '{app_info.get('app_name')}': "
                        f"Duplicidade encontrada para '{record.dado_normalizado}' (Tipo: {record.tipo_validacao}). "
                        f"Registro existente ID: {duplicate_record_found.id}."
                    )
                else:
                    actions_summary["duplicate_check_action"] = {
                        "code": rule_code,
                        "status": rule_metadata["result_status"] if rule_metadata else "Executed",
                        "message": f"Dado '{record.dado_normalizado}' não é duplicado no histórico.",
                        "is_duplicate": False
                    }
                    logger.info(f"[Ação] Aplicação '{app_info.get('app_name')}': Nenhum duplicado encontrado para '{record.dado_normalizado}'.")

            except Exception as e:
                actions_summary["duplicate_check_action"] = {
                    "code": rule_code,
                    "status": rule_metadata["fail_status"] if rule_metadata else "Error",
                    "message": f"Erro inesperado ao verificar duplicidade: {e}"
                }
                logger.error(f"[Ação] Erro ao verificar duplicidade para registro ID {record.id}: {e}", exc_info=True)
        else:
            actions_summary["duplicate_check_action"] = {
                "code": rule_code,
                "status": "Not Applicable",
                "message": "Regra de verificação de duplicidade não aplicada (registro inválido, sem permissão ou dados normalizados para comparação)."
            }
            logger.debug(f"Verificação de duplicidade não aplicada para registro ID {record.id}. Válido: {record.is_valido}, Permissão: {app_info.get('can_check_duplicates', False)}, Dado Normalizado: {bool(record.dado_normalizado)}.")