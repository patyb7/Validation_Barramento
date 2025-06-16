# app/rules/decision_rules.py

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.database.repositories import ValidationRecordRepository
from app.models.validation_record import ValidationRecord

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class DecisionRules:
    """
    Aplica regras de decisão de negócio após a validação inicial de um dado.
    Estas regras podem incluir ações como:
    - Soft delete de registros inválidos com base em permissões da API Key.
    - Verificação de duplicidade de dados validados.
    - Outras ações customizadas baseadas nos metadados da aplicação.
    """

    def __init__(self, repo: ValidationRecordRepository):
        self.repo = repo

    def apply_post_validation_actions(self, record: ValidationRecord, app_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplica um conjunto de regras de decisão de negócio a um registro de validação
        recém-criado, com base nas permissões da aplicação chamadora.

        Args:
            record: O objeto ValidationRecord recém-criado/salvo no banco de dados.
            app_info: Dicionário contendo os metadados da aplicação (API Key).
                      Esperado campos como 'app_name', 'can_delete_invalid', 'can_check_duplicates'.

        Returns:
            Um dicionário com o resultado das ações pós-validação,
            indicando quais regras foram aplicadas e seus impactos.
        """
        app_name = app_info.get("app_name", "Aplicação Desconhecida")
        actions_log = {}

        logger.info(f"Iniciando aplicação de regras de decisão para registro ID: {record.id}, App: '{app_name}'")

        self._rule_soft_delete_invalid_records(record, app_info, actions_log)
        self._rule_check_duplicates(record, app_info, actions_log)

        logger.info(f"Regras de decisão aplicadas para registro ID: {record.id}. Resultados: {actions_log}")
        return actions_log

    def _rule_soft_delete_invalid_records(self, record: ValidationRecord, app_info: Dict[str, Any], actions_log: Dict[str, Any]):
        """
        Regra Privada: Se o registro é inválido e a aplicação tem a permissão 'can_delete_invalid',
        marca o registro para soft delete no banco de dados.
        """
        if not record.valido and app_info.get("can_delete_invalid", False):
            logger.info(f"Tentando soft delete para registro ID {record.id} (inválido). App '{app_info.get('app_name')}' tem permissão.")
            try:
                success = self.repo.soft_delete_record_by_id(record.id)
                if success:
                    record.is_deleted = True
                    record.deleted_at = datetime.now() 
                    actions_log["soft_delete_invalid"] = True
                    actions_log["soft_delete_invalid_message"] = "Registro inválido foi marcado para soft delete com sucesso."
                    logger.info(f"[Decisão] Registro ID {record.id} (Inválido) marcado para soft delete pela aplicação '{app_info.get('app_name')}'.")
                else:
                    actions_log["soft_delete_invalid"] = False
                    actions_log["soft_delete_invalid_message"] = "Falha ao marcar registro inválido para soft delete (repositório retornou falha)."
                    logger.warning(f"[Decisão] Falha ao marcar registro ID {record.id} para soft delete. App: '{app_info.get('app_name')}'.")
            except Exception as e:
                actions_log["soft_delete_invalid"] = False
                actions_log["soft_delete_invalid_message"] = f"Erro inesperado ao tentar soft delete de registro inválido: {e}"
                logger.error(f"[Decisão] Erro ao tentar soft delete para registro ID {record.id}: {e}", exc_info=True)
        else:
            actions_log["soft_delete_invalid"] = False
            actions_log["soft_delete_invalid_message"] = "Regra de soft delete de inválidos não aplicada (registro válido ou sem permissão)."
            logger.debug(f"Soft delete de inválidos não aplicado para registro ID {record.id}. Válido: {record.valido}, Permissão: {app_info.get('can_delete_invalid', False)}.")


    def _rule_check_duplicates(self, record: ValidationRecord, app_info: Dict[str, Any], actions_log: Dict[str, Any]):
        """
        Regra Privada: Se o registro é válido e a aplicação tem a permissão 'can_check_duplicates',
        verifica se já existe um registro similar no banco de dados.
        """
        # A verificação de duplicidade faz sentido para dados válidos
        # e se o campo 'dado_normalizado' está presente.
        if record.valido and app_info.get("can_check_duplicates", False) and record.dado_normalizado: # Renomeado
            logger.info(f"Tentando verificar duplicidade para registro ID {record.id}. App '{app_info.get('app_name')}' tem permissão.")
            try:
                duplicate_record_found: Optional[ValidationRecord] = self.repo.find_duplicate_record(
                    dado_normalizado=record.dado_normalizado, # Renomeado
                    tipo_validacao=record.tipo_validacao,
                    exclude_record_id=record.id
                )

                if duplicate_record_found:
                    actions_log["is_duplicate"] = True
                    actions_log["duplicate_id"] = duplicate_record_found.id
                    actions_log["duplicate_message"] = (
                        f"Dado '{record.dado_normalizado}' (Tipo: {record.tipo_validacao}) é um DUPLICADO. " # Renomeado
                        f"Registro existente ID: {duplicate_record_found.id}."
                    )
                    logger.warning(
                        f"[Decisão] Aplicação '{app_info.get('app_name')}': "
                        f"Duplicidade encontrada para '{record.dado_normalizado}' (Tipo: {record.tipo_validacao}). " # Renomeado
                        f"Registro existente ID: {duplicate_record_found.id}."
                    )
                else:
                    actions_log["is_duplicate"] = False
                    actions_log["duplicate_message"] = f"Dado '{record.dado_normalizado}' não é duplicado no histórico." # Renomeado
                    logger.info(f"[Decisão] Aplicação '{app_info.get('app_name')}': Nenhum duplicado encontrado para '{record.dado_normalizado}'.") # Renomeado

            except Exception as e:
                actions_log["is_duplicate"] = False
                actions_log["duplicate_message"] = f"Erro inesperado ao verificar duplicidade: {e}"
                logger.error(f"[Decisão] Erro ao verificar duplicidade para registro ID {record.id}: {e}", exc_info=True)
        else:
            actions_log["is_duplicate"] = False
            actions_log["duplicate_message"] = "Regra de verificação de duplicidade não aplicada (registro inválido, sem permissão ou dados normalizados para comparação)."
            logger.debug(f"Verificação de duplicidade não aplicada para registro ID {record.id}. Válido: {record.valido}, Permissão: {app_info.get('can_check_duplicates', False)}, Dado Normalizado: {bool(record.dado_normalizado)}.") # Renomeado