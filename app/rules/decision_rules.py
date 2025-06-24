# app/rules/decision_rules.py

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from app.database.repositories.validation_record_repository import ValidationRecordRepository
from app.models.validation_record import ValidationRecord

logger = logging.getLogger(__name__)

class DecisionRules:
    """
    Classe responsável por aplicar regras de negócio e tomar decisões
    com base nos resultados da validação e no contexto da aplicação/cliente.
    Gerencia a lógica de Golden Record, duplicidade e ações como soft-delete.
    """
    
    # Definição das regras de negócio (exemplo)
    BUSINESS_RULES = {
        "RN_TEL_BR_MOBILE_APP": {
            "type": "Telefone",
            "name": "Mobile BR",
            "description": "Regra estrita para celulares brasileiros em apps específicos.",
            "result_status": "APROVADO",
            "fail_status": "REPROVADO",
            "impact": "Pode bloquear o cadastro/uso de telefones que não atendem ao padrão estrito."
        },
        "RN_CEP_PJ_CLIENT": {
            "type": "CEP",
            "name": "CEP Cliente PJ",
            "description": "Validação adicional para CEPs de clientes pessoa jurídica.",
            "result_status": "APROVADO",
            "fail_status": "REPROVADO",
            "impact": "Pode requerer um CEP mais granular ou de áreas comerciais."
        },
        "RN_DUPLICIDADE_DADO": {
            "type": "Verificação",
            "name": "Verificação de Duplicidade",
            "description": "Identifica se um dado validado já existe na base de Golden Records ou validações anteriores.",
            "result_status": "VERIFICADO",
            "fail_status": "N/A",
            "impact": "Pode disparar alertas ou impedir a criação de novos registros duplicados."
        },
        "RN_SOFT_DELETE_INVALIDOS": {
            "type": "Ação",
            "name": "Soft Delete de Inválidos",
            "description": "Marca registros de dados inválidos para exclusão lógica (soft-delete).",
            "result_status": "EXECUTADO",
            "fail_status": "FALHA",
            "impact": "Registros inválidos são ocultados de consultas padrão, mas podem ser restaurados."
        },
        "RN_GOLDEN_RECORD_CRITERIA": {
            "type": "Qualificação",
            "name": "Critério de Golden Record",
            "description": "Define as condições para um registro ser qualificado como Golden Record.",
            "result_status": "QUALIFICADO",
            "fail_status": "N/A",
            "impact": "Garante a unicidade e a melhor versão do dado no sistema."
        },
        "RN_NEGOCIO_PADRAO": {
            "type": "Geral",
            "name": "Regra Padrão",
            "description": "Regra de negócio padrão aplicada quando nenhuma outra específica se aplica.",
            "result_status": "N/A",
            "fail_status": "N/A",
            "impact": "Nenhum impacto direto pela regra de negócio; serve como marcador padrão."
        }
    }

    # Exemplos de configurações de aplicativos que podem influenciar as regras
    # Essas configurações viriam da APIKeyManager
    APPS_REQUIRING_STRICT_PHONE = ["Sistema de Seguros", "Sistema de Bancos Digitais"]
    APPS_CAN_SOFT_DELETE = ["Sistema de Onboarding", "Sistema de Conformidade"]
    APPS_CAN_CHECK_DUPLICATES = ["Sistema de Cadastro Geral", "Sistema de Compliance"]

    def __init__(self, repo: ValidationRecordRepository):
        self.repo = repo
        logger.info("DecisionRules inicializado.")

    async def apply_rules(self, record: ValidationRecord, app_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplica regras de negócio ao registro de validação.
        
        Args:
            record (ValidationRecord): O objeto do registro de validação.
            app_info (Dict[str, Any]): Informações sobre o aplicativo que fez a requisição.
        
        Returns:
            Dict[str, Any]: Um resumo das ações e regras aplicadas.
        """
        logger.debug(f"Aplicando regras de negócio para o registro ID: {record.id}, App: {app_info.get('app_name')}")
        actions_summary = {}
        app_name = app_info.get("app_name", "Desconhecido")
        
        # Inicializa um dicionário para armazenar as atualizações a serem persistidas
        updates_to_db: Dict[str, Any] = {}

        # --- Regra Específica: Telefone Estrito para Certos Apps ---
        if record.tipo_validacao == "telefone" and app_name in self.APPS_REQUIRING_STRICT_PHONE:
            if not record.is_valido:
                # Se o telefone é inválido E o app requer validação estrita
                record.regra_negocio_codigo = "RN_TEL_BR_MOBILE_APP" # Pode ser uma regra de falha específica
                record.regra_negocio_descricao = self.BUSINESS_RULES["RN_TEL_BR_MOBILE_APP"]["description"] + " (Falha)"
                record.regra_negocio_tipo = self.BUSINESS_RULES["RN_TEL_BR_MOBILE_APP"]["type"]
                actions_summary["strict_phone_rule"] = {"status": "APPLIED_FAILURE", "message": "Regra de telefone estrito falhou."}
            else:
                record.regra_negocio_codigo = "RN_TEL_BR_MOBILE_APP"
                record.regra_negocio_descricao = self.BUSINESS_RULES["RN_TEL_BR_MOBILE_APP"]["description"] + " (Sucesso)"
                record.regra_negocio_tipo = self.BUSINESS_RULES["RN_TEL_BR_MOBILE_APP"]["type"]
                actions_summary["strict_phone_rule"] = {"status": "APPLIED_SUCCESS", "message": "Regra de telefone estrito aplicada com sucesso."}
            
            # Adiciona as alterações ao dicionário de updates
            updates_to_db["regra_negocio_codigo"] = record.regra_negocio_codigo
            updates_to_db["regra_negocio_descricao"] = record.regra_negocio_descricao
            updates_to_db["regra_negocio_tipo"] = record.regra_negocio_tipo


        # --- Ação: Soft Delete para Dados Inválidos (se permitido pelo app) ---
        if not record.is_valido and app_name in self.APPS_CAN_SOFT_DELETE:
            record.is_deleted = True
            record.deleted_at = datetime.now(timezone.utc)
            record.status_qualificacao = "UNQUALIFIED" # Exemplo de status
            
            updates_to_db["is_deleted"] = True
            updates_to_db["deleted_at"] = record.deleted_at
            updates_to_db["status_qualificacao"] = record.status_qualificacao
            
            actions_summary["soft_delete_action"] = {"status": "EXECUTADO", "message": "Registro inválido soft-deletado."}
            logger.info(f"Registro {record.id} marcado para soft-delete devido à invalidez e permissão do app '{app_name}'.")

        # --- Ação: Verificação de Duplicidade (se permitido pelo app) ---
        if record.is_valido and app_name in self.APPS_CAN_CHECK_DUPLICATES:
            duplicate_record = await self.repo.find_duplicate_record(
                dado_normalizado=record.dado_normalizado,
                tipo_validacao=record.tipo_validacao,
                app_name=record.app_name, # Pode-se verificar duplicidade apenas dentro do mesmo app ou globalmente
                exclude_record_id=record.id # Exclui o próprio registro que está sendo validado
            )
            
            if duplicate_record:
                actions_summary["duplicate_check_action"] = {
                    "status": "VERIFICADO_DUPLICADO",
                    "message": f"Duplicado encontrado com ID: {duplicate_record.id}",
                    "is_duplicate": True,
                    "duplicate_record_id": str(duplicate_record.id)
                }
                logger.info(f"Duplicado encontrado para dado '{record.dado_normalizado}' (Tipo: {record.tipo_validacao}). ID do duplicado: {duplicate_record.id}.")
                record.status_qualificacao = "PENDING_DUPLICATE_REVIEW" # Exemplo de status
                updates_to_db["status_qualificacao"] = record.status_qualificacao

            else:
                actions_summary["duplicate_check_action"] = {
                    "status": "VERIFICADO_UNICO",
                    "message": "Nenhum duplicado encontrado.",
                    "is_duplicate": False
                }
                record.status_qualificacao = "QUALIFIED" if record.is_valido else record.status_qualificacao # Qualificado se válido e único
                updates_to_db["status_qualificacao"] = record.status_qualificacao
                logger.debug(f"Nenhum duplicado encontrado para dado '{record.dado_normalizado}'.")
            
            # --- Regra: Gestão de Golden Record ---
            # Se o dado é válido e não é um duplicado existente, considere-o para Golden Record
            if record.is_valido and not duplicate_record:
                # Primeiro, marque qualquer GR existente para este dado/tipo como não-GR
                await self.repo.set_golden_record_false_for_normalized_data(
                    dado_normalizado=record.dado_normalizado,
                    tipo_validacao=record.tipo_validacao,
                    exclude_id=record.id
                )
                # Define o registro atual como Golden Record
                record.is_golden_record = True
                record.golden_record_id = record.id # O próprio ID é o Golden Record ID
                record.status_qualificacao = "QUALIFIED_GOLDEN"
                
                updates_to_db["is_golden_record"] = True
                updates_to_db["golden_record_id"] = record.golden_record_id
                updates_to_db["status_qualificacao"] = record.status_qualificacao

                actions_summary["golden_record_action"] = {
                    "status": "SET_GOLDEN",
                    "message": "Registro definido como Golden Record."
                }
                logger.info(f"Registro {record.id} definido como Golden Record para '{record.dado_normalizado}'.")
            elif record.is_valido and duplicate_record:
                # Se é válido mas é um duplicado, ele aponta para o Golden Record existente
                record.golden_record_id = duplicate_record.golden_record_id if duplicate_record.is_golden_record else duplicate_record.id
                record.status_qualificacao = "QUALIFIED_DUPLICATE"
                
                updates_to_db["golden_record_id"] = record.golden_record_id
                updates_to_db["status_qualificacao"] = record.status_qualificacao

                actions_summary["golden_record_action"] = {
                    "status": "IS_DUPLICATE_OF_GOLDEN",
                    "message": f"Registro válido, mas duplicado do Golden Record: {record.golden_record_id}"
                }
            elif not record.is_valido:
                 record.status_qualificacao = "UNQUALIFIED"
                 updates_to_db["status_qualificacao"] = record.status_qualificacao


        # Se nenhuma regra de negócio específica foi atribuída pelo validador ou por esta função, usa a regra padrão
        if record.regra_negocio_codigo is None or "regra_negocio_codigo" not in updates_to_db: # Verifica se já foi setada
            rule_code = "RN_NEGOCIO_PADRAO"
            record.regra_negocio_codigo = rule_code
            record.regra_negocio_descricao = self.BUSINESS_RULES[rule_code]["description"]
            record.regra_negocio_tipo = self.BUSINESS_RULES[rule_code]["type"]
            
            updates_to_db["regra_negocio_codigo"] = record.regra_negocio_codigo
            updates_to_db["regra_negocio_descricao"] = record.regra_negocio_descricao
            updates_to_db["regra_negocio_tipo"] = record.regra_negocio_tipo

            actions_summary["default_business_rule"] = {"status": "APPLIED", "message": "Regra de negócio padrão aplicada."}
        
        # Salva as alterações no registro no banco de dados
        # Passa apenas os campos que foram modificados e precisam ser atualizados no DB.
        if updates_to_db:
            await self.repo.update_record(record.id, updates_to_db)

        logger.debug(f"Regras de negócio aplicadas. Sumário: {actions_summary}")
        return actions_summary
