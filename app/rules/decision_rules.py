# app/rules/decision_rules.py

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
import uuid

from app.models.validation_record import ValidationRecord
from app.database.repositories.validation_record_repository import ValidationRecordRepository
from app.database.repositories.qualification_repository import QualificationRepository 
from app.database.repositories.validation_record_repository import ValidationRecordRepository

logger = logging.getLogger(__name__)

class DecisionRules:
    """
    Classe para aplicar regras de negócio após a validação inicial de um dado.
    Decide se um registro deve ser um Golden Record, ir para qualificação pendente,
    ou ser marcado como inválido.
    """
    def __init__(self,
                 validation_repo: ValidationRecordRepository,
                 qualification_repo: QualificationRepository):
        self.validation_repo = validation_repo
        self.qualification_repo = qualification_repo
        logger.info("DecisionRules inicializado.")

    async def apply_rules(self, record: ValidationRecord, app_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplica um conjunto de regras de negócio a um ValidationRecord recém-criado.
        Determina o status de qualificação do registro (Golden Record, Pendente, Inválido).

        Args:
            record (ValidationRecord): O registro de validação recém-criado.
            app_info (Dict[str, Any]): Informações da aplicação que originou a validação.

        Returns:
            Dict[str, Any]: Um resumo das ações tomadas (para logging/resposta da API).
        """
        actions_summary = {
            "is_golden_record_candidate": False,
            "status_qualificacao_set": "UNQUALIFIED", # Default
            "moved_to_qualificacoes_pendentes_queue": False,
            "moved_to_invalid_archive": False,
            "client_entity_created_or_updated": False,
            "reason": []
        }

        # Step 1: Avaliar se o registro é um candidato a Golden Record (100% validado nos campos críticos)
        is_golden_record_candidate, golden_record_reasons = self._evaluate_golden_record_candidacy(record)
        actions_summary["is_golden_record_candidate"] = is_golden_record_candidate
        actions_summary["reason"].extend(golden_record_reasons)

        record_needs_revalidation = False
        revalidation_reason = ""

        individual_validations = record.validation_details.get("individual_validations", {})

        # Lógica específica para telefone: se for válido mas não encontrado (RN_TEL004), vai para pendente.
        # Isso sobrepõe o status de Golden Record Candidato se a regra de negócio assim desejar.
        celular_validation = individual_validations.get("celular")
        if celular_validation:
            if celular_validation["is_valid"] and celular_validation["business_rule_applied"]["code"] == "RN_TEL004":
                record_needs_revalidation = True
                revalidation_reason = "Celular válido (formato), mas não encontrado na base cadastral simulada. Revalidação agendada."
                actions_summary["reason"].append("celular_pending_revalidation")
                actions_summary["status_qualificacao_set"] = "PENDING_REVALIDATION"
                is_golden_record_candidate = False # Não pode ser Golden Record direto se precisa de revalidação
            elif not celular_validation["is_valid"]: # Se celular é inválido por outros motivos (ex: formato)
                actions_summary["reason"].append("celular_invalid_not_pending")
                actions_summary["status_qualificacao_set"] = "UNQUALIFIED"
                is_golden_record_candidate = False # Não pode ser Golden Record

        # Similar para telefone_fixo, se você quiser a mesma lógica
        telefone_fixo_validation = individual_validations.get("telefone_fixo")
        if telefone_fixo_validation and not record_needs_revalidation: # Evita duplicidade se celular já marcou
            if telefone_fixo_validation["is_valid"] and telefone_fixo_validation["business_rule_applied"]["code"] == "RN_TEL004":
                record_needs_revalidation = True
                revalidation_reason = "Telefone fixo válido (formato), mas não encontrado na base cadastral simulada. Revalidação agendada."
                actions_summary["reason"].append("telefone_fixo_pending_revalidation")
                actions_summary["status_qualificacao_set"] = "PENDING_REVALIDATION"
                is_golden_record_candidate = False
            elif not telefone_fixo_validation["is_valid"]:
                actions_summary["reason"].append("telefone_fixo_invalid_not_pending")
                actions_summary["status_qualificacao_set"] = "UNQUALIFIED"
                is_golden_record_candidate = False

        # Step 3: Tomar decisão final sobre o ValidationRecord
        if is_golden_record_candidate:
            record.is_golden_record = True
            record.status_qualificacao = "QUALIFIED"
            actions_summary["status_qualificacao_set"] = "QUALIFIED"
            logger.info(f"Registro {record.id} é um candidato a Golden Record e QUALIFICADO.")

            # Tenta criar/atualizar o Client Entity (Golden Record no mestre)
            # Para pessoa_completa, o documento principal seria o CPF
            cpf_validation = individual_validations.get("cpf")
            main_document_normalized = cpf_validation.get("dado_normalizado") if cpf_validation else None

            if main_document_normalized:
                client_entity = await self.qualification_repo.get_client_entity_by_main_document(main_document_normalized)
                consolidated_data = self._consolidate_golden_record_data(record)

                # Estes IDs apontam para o ValidationRecord que deu origem ao Golden Record de cada tipo
                # Para uma validação 'pessoa_completa', o próprio record.id pode ser o ID do golden record
                # para todos os seus campos, se ele é o primeiro e mais completo.
                golden_record_ids_to_link = {
                    "golden_record_cpf_cnpj_id": record.id if (cpf_validation and cpf_validation.get("is_valid") and cpf_validation["business_rule_applied"]["code"] == "RN_DOC001") else None,
                    "golden_record_address_id": record.id if (individual_validations.get("endereco") and individual_validations["endereco"].get("is_valid") and individual_validations["endereco"].get("business_rule_applied", {}).get("code") == "RN_ADDR001") else None,
                    "golden_record_phone_id": record.id if (individual_validations.get("celular") and individual_validations["celular"].get("is_valid") and individual_validations["celular"]["business_rule_applied"]["code"] == "RN_TEL001") else None,
                    "golden_record_email_id": record.id if (individual_validations.get("email") and individual_validations["email"].get("is_valid") and individual_validations["email"].get("business_rule_applied", {}).get("code") == "RN_EMAIL002") else None,
                    "golden_record_cep_id": record.id if (individual_validations.get("cep") and individual_validations["cep"].get("is_valid") and individual_validations["cep"].get("business_rule_applied", {}).get("code") == "VAL_CEP001") else None,
                    "golden_record_rg_id": record.id if (individual_validations.get("rg") and individual_validations["rg"].get("is_valid") and individual_validations["rg"].get("business_rule_applied", {}).get("code") == "RN_RG001") else None,
                }
                
                if client_entity:
                    # Atualiza o Golden Record existente
                    update_data = {
                        "consolidated_data": consolidated_data,
                        **golden_record_ids_to_link
                    }
                    updated_entity = await self.qualification_repo.update_client_entity(client_entity["id"], update_data)
                    if updated_entity:
                        record.golden_record_id = updated_entity["id"] # Linka o validation_record ao GR
                        actions_summary["client_entity_created_or_updated"] = True
                        logger.info(f"Golden Record existente atualizado para cliente {main_document_normalized}. ID: {updated_entity['id']}")
                    else:
                        logger.error(f"Falha ao atualizar Golden Record existente para {main_document_normalized}.")
                else:
                    # Cria um novo Golden Record
                    new_entity_data = {
                        "main_document_normalized": main_document_normalized,
                        "consolidated_data": consolidated_data,
                        "relationship_type": "Pessoa Fisica", # Exemplo, pode vir de outro campo
                        "cclub": record.client_identifier, # Pode ser o client_identifier ou outro campo dos dados de entrada
                        **golden_record_ids_to_link
                    }
                    new_entity = await self.qualification_repo.create_client_entity(new_entity_data)
                    if new_entity:
                        record.golden_record_id = new_entity["id"] # Linka o validation_record ao GR
                        actions_summary["client_entity_created_or_updated"] = True
                        logger.info(f"Novo Golden Record criado para cliente {main_document_normalized}. ID: {new_entity['id']}")
                    else:
                        logger.error(f"Falha ao criar novo Golden Record para {main_document_normalized}.")
            else:
                logger.warning(f"Não foi possível determinar o documento principal normalizado para criar/atualizar o Golden Record para o registro {record.id}. O registro não será um GR na tabela de entidades de cliente.")
                record.is_golden_record = False # Se não tem documento principal, não pode ser GR
                record.status_qualificacao = "UNQUALIFIED"
                actions_summary["status_qualificacao_set"] = "UNQUALIFIED"


        elif record_needs_revalidation:
            # Se precisa de revalidação, adiciona à fila de pendentes
            record.is_golden_record = False # Não é um Golden Record ainda
            record.status_qualificacao = "PENDING_REVALIDATION"
            actions_summary["status_qualificacao_set"] = "PENDING_REVALIDATION"
            actions_summary["moved_to_qualificacoes_pendentes_queue"] = True
            
            # CORRIGIDO: Usar a classe QualificacaoPendente renomeada
            pending_rec = QualificacaoPendente(
                validation_record_id=record.id,
                client_identifier=record.client_identifier,
                validation_type=record.tipo_validacao, # Tipo da validação composta 'pessoa_completa'
                status_motivo=revalidation_reason,
                attempt_count=0,
                last_attempt_at=None,
                scheduled_next_attempt_at=datetime.now(timezone.utc) + timedelta(days=1) # Agendar para amanhã
            )
            await self.qualification_repo.create_pending_qualification(pending_rec)
            logger.info(f"Registro {record.id} marcado como PENDING_REVALIDATION e adicionado à fila de qualificações pendentes.")

        else:
            # Não é Golden Record e não vai para pendente (inválido ou inconsistente)
            record.is_golden_record = False
            record.status_qualificacao = "UNQUALIFIED"
            actions_summary["status_qualificacao_set"] = "UNQUALIFIED"
            logger.info(f"Registro {record.id} marcado como UNQUALIFIED.")
            # O microserviço de revalidação moveria para inválidos após 20 dias,
            # ou uma regra mais rígida aqui poderia mover direto para inválidos
            # se a falha for crítica e não revalidável (ex: CPF com checksum inválido).
        
        # Salva as atualizações no ValidationRecord (is_golden_record, status_qualificacao, golden_record_id)
        await self.validation_repo.update_record(record.id, {
            "is_golden_record": record.is_golden_record,
            "status_qualificacao": record.status_qualificacao,
            "golden_record_id": record.golden_record_id
        })

        return actions_summary

    def _evaluate_golden_record_candidacy(self, record: ValidationRecord) -> (bool, List[str]):
        """
        Avalia se um ValidationRecord é um candidato a Golden Record com base
        em suas validações individuais para o tipo 'pessoa_completa'.
        Retorna True/False e uma lista de razões.
        """
        if record.tipo_validacao != "pessoa_completa":
            return False, ["A avaliação de Golden Record aplica-se apenas a 'pessoa_completa'."]

        critical_fields_valid = True
        reasons = []
        
        individual_validations = record.validation_details.get("individual_validations", {})

        # CPF: Deve ser válido e ENCONTRADO na base cadastral simulada (RN_DOC001)
        cpf_val = individual_validations.get("cpf")
        if not (cpf_val and cpf_val.get("is_valid") and cpf_val.get("business_rule_applied", {}).get("code") == "RN_DOC001"):
            critical_fields_valid = False
            reasons.append("CPF não é válido ou não encontrado na base cadastral simulada.")
        
        # Nome: Deve ser válido
        nome_val = individual_validations.get("nome")
        if not (nome_val and nome_val.get("is_valid")):
            critical_fields_valid = False
            reasons.append("Nome não é válido.")

        # Data de Nascimento: Deve ser válida
        data_nasc_val = individual_validations.get("data_nascimento")
        if not (data_nasc_val and data_nasc_val.get("is_valid")):
            critical_fields_valid = False
            reasons.append("Data de nascimento não é válida.")

        # Email: Deve ser válido e domínio resolvível (RN_EMAIL002)
        email_val = individual_validations.get("email")
        if not (email_val and email_val.get("is_valid") and email_val.get("business_rule_applied", {}).get("code") == "RN_EMAIL002"):
            critical_fields_valid = False
            reasons.append("Email não é válido ou o domínio não é resolvível.")

        # Endereço: Deve ser válido e CONSISTENTE. Se cair em RN_ADDR006 ou RN_ADDR004, não é Golden Record.
        endereco_val = individual_validations.get("endereco")
        # RN_ADDR001 = Endereço válido e completo
        if not (endereco_val and endereco_val.get("is_valid") and endereco_val.get("business_rule_applied", {}).get("code") == "RN_ADDR001"): 
            critical_fields_valid = False
            reasons.append("Endereço não é válido ou não é 100% consistente (ex: CEP não encontrado externamente ou inconsistente).")

        # Celular: Para ser Golden Record DIRETO, deve ser válido e ENCONTRADO na base simulada (RN_TEL001).
        # Se for RN_TEL004 (válido, mas não encontrado), NÃO É um Golden Record imediato, vai para pendente.
        celular_val = individual_validations.get("celular")
        if not (celular_val and celular_val.get("is_valid") and celular_val.get("business_rule_applied", {}).get("code") == "RN_TEL001"):
            critical_fields_valid = False
            # A razão específica para celular (RN_TEL004) será tratada fora desta função para pendência.
            # Aqui, apenas indicamos que não é 100% Golden Record.
            if not (celular_val and celular_val.get("is_valid")):
                 reasons.append("Celular não é válido.")
            elif celular_val.get("business_rule_applied", {}).get("code") == "RN_TEL004":
                 reasons.append("Celular válido (formato), mas não encontrado na base cadastral (requer revalidação para GR).")
            else:
                 reasons.append("Celular não está 100% qualificado para Golden Record.")


        # RG: Deve ser válido e ATIVO na base (RN_RG001)
        rg_val = individual_validations.get("rg")
        if not (rg_val and rg_val.get("is_valid") and rg_val.get("business_rule_applied", {}).get("code") == "RN_RG001"):
            critical_fields_valid = False
            reasons.append("RG não é válido ou não está ativo na base cadastral simulada.")

        return critical_fields_valid, reasons
    
    def _consolidate_golden_record_data(self, record: ValidationRecord) -> Dict[str, Any]:
        """
        Consolida os dados normalizados das validações individuais para o Golden Record.
        Prioriza dados de sub-validações válidas.
        """
        consolidated_data = {}
        individual_validations = record.validation_details.get("individual_validations", {})

        # Campos diretos da validação composta
        for key in ["nome", "data_nascimento", "sexo"]:
            if individual_validations.get(key) and individual_validations[key].get("is_valid"):
                consolidated_data[key] = individual_validations[key].get("dado_normalizado")
        
        # Campos que são frequentemente identificadores ou de alta importância
        # CPF/CNPJ
        cpf_val = individual_validations.get("cpf")
        if cpf_val and cpf_val.get("is_valid") and cpf_val.get("business_rule_applied", {}).get("code") == "RN_DOC001":
            consolidated_data["cpf_cnpj"] = cpf_val.get("dado_normalizado")
        
        # Email
        email_val = individual_validations.get("email")
        if email_val and email_val.get("is_valid") and email_val.get("business_rule_applied", {}).get("code") == "RN_EMAIL002":
            consolidated_data["email"] = email_val.get("dado_normalizado")
        
        # Celular (apenas se RN_TEL001, caso contrário, será tratado como pendente ou inválido)
        celular_val = individual_validations.get("celular")
        if celular_val and celular_val.get("is_valid") and celular_val.get("business_rule_applied", {}).get("code") == "RN_TEL001":
            consolidated_data["celular"] = celular_val.get("dado_normalizado")

        # Telefone Fixo (apenas se RN_TEL001)
        telefone_fixo_val = individual_validations.get("telefone_fixo")
        if telefone_fixo_val and telefone_fixo_val.get("is_valid") and telefone_fixo_val.get("business_rule_applied", {}).get("code") == "RN_TEL001":
            consolidated_data["telefone_fixo"] = telefone_fixo_val.get("dado_normalizado")

        # RG
        rg_val = individual_validations.get("rg")
        if rg_val and rg_val.get("is_valid") and rg_val.get("business_rule_applied", {}).get("code") == "RN_RG001":
            consolidated_data["rg"] = rg_val.get("dado_normalizado")

        # Endereço (somente se RN_ADDR001)
        endereco_val = individual_validations.get("endereco")
        if endereco_val and endereco_val.get("is_valid") and endereco_val.get("business_rule_applied", {}).get("code") == "RN_ADDR001":
            consolidated_data["endereco"] = endereco_val.get("dado_normalizado")
            consolidated_data["cep"] = individual_validations.get("cep", {}).get("dado_normalizado") # Inclui o CEP também

        # Remove None values
        return {k: v for k, v in consolidated_data.items() if v is not None}
