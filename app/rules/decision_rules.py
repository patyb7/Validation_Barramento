# app/rules/decision_rules.py
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
import uuid

from app.models.validation_record import ValidationRecord
from app.database.repositories.validation_record_repository import ValidationRecordRepository
from app.database.repositories.qualification_repository import QualificationRepository 
from app.models.qualificacao_pendente import QualificacaoPendente

logger = logging.getLogger(__name__)

class DecisionRules:
    """
    Classe para aplicar regras de negócio após a validação inicial de um dado.
    Decide se um registro deve ser um Golden Record, ir para qualificação pendente,
    ou ser marcado como inválido.
    """
    
    # 2. Configuração das Regras de Negócio: Externalização
    # Define as regras de negócio críticas para a elegibilidade do Golden Record
    CRITICAL_GOLDEN_RECORD_RULES = {
        "cpf": "RN_DOC001",     # CPF válido e ENCONTRADO
        "nome": None,           # Nome válido (apenas is_valid)
        "data_nascimento": None, # Data de nascimento válida (apenas is_valid)
        "email": "RN_EMAIL002", # Email válido e domínio resolvível
        "endereco": "RN_ADDR001",# Endereço válido e CONSISTENTE
        "celular": "RN_TEL001", # Celular válido e ENCONTRADO
        "rg": "RN_RG001",       # RG válido e ATIVO
        "telefone_fixo": "RN_TEL001", # Telefone Fixo válido e ENCONTRADO - Removido daqui para ser tratado por REVALIDATION_PHONE_RULES
        "cep": "VAL_CEP001" # CEP válido e consistente (pode ser inferido do endereço)
    }

    # Define campos que, se forem RN_TEL004, levam à revalidação
    REVALIDATION_PHONE_RULES = ["RN_TEL004"] # Válido formato, mas não encontrado

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
            app_info (Dict[str, Any]): Informações da aplicação que originou a validação,
                                        pode incluir 'relationship_type' e 'cclub_identifier'.

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

        # Inicializa flags e razões de revalidação
        record_needs_revalidation = False
        revalidation_reason = ""
        
        individual_validations = record.validation_details.get("individual_validations", {})

        # --- CORREÇÃO APLICADA AQUI ---
        # A lógica para decidir sobre a revalidação ou desqualificação de telefones
        # deve vir antes da avaliação geral de Golden Record, pois ela pode anular
        # a candidatura a Golden Record e definir um status específico.
        for phone_field in ["celular", "telefone_fixo"]:
            phone_validation = individual_validations.get(phone_field)
            if phone_validation:
                phone_rule_code = phone_validation.get("business_rule_applied", {}).get("code")

                # Prioriza a regra de revalidação (RN_TEL004)
                if phone_rule_code in self.REVALIDATION_PHONE_RULES:
                    record_needs_revalidation = True
                    revalidation_reason = f"{phone_field.capitalize()}: Telefone válido (formato), mas não encontrado na base cadastral simulada. Revalidação agendada."
                    actions_summary["reason"].append(f"{phone_field}_pending_revalidation")
                    # Define o status provisório para PENDING_REVALIDATION.
                    # Ele será consolidado na decisão final.
                    actions_summary["status_qualificacao_set"] = "PENDING_REVALIDATION"
                    break # Se um telefone já indica revalidação, paramos aqui para esse loop
                
                # Se não é uma regra de revalidação, mas o campo não é válido por outros motivos
                elif not phone_validation["is_valid"]: 
                    actions_summary["reason"].append(f"{phone_field}_invalid_not_pending")
                    # Se um telefone é inválido (e não é para revalidação), o registro é UNQUALIFIED
                    actions_summary["status_qualificacao_set"] = "UNQUALIFIED"
                    # Isso garante que se houver um telefone inválido (não RN_TEL004), o registro não será GR.
                    # Não colocamos break aqui para que outros telefones possam ser verificados para razões.
        # --- FIM DA CORREÇÃO ---


        # Step 1: Avaliar se o registro é um candidato a Golden Record
        # Esta avaliação de Golden Record agora deve considerar o que as validações de telefone já definiram.
        # Se 'status_qualificacao_set' já é "UNQUALIFIED" ou "PENDING_REVALIDATION" pelos telefones,
        # ele não deve mais ser um candidato a Golden Record.
        is_golden_record_candidate, golden_record_reasons = await self._evaluate_golden_record_candidacy(record) 

        # Se já foi marcado para revalidação ou desqualificado por telefone, a candidatura a GR é anulada
        if actions_summary["status_qualificacao_set"] in ["UNQUALIFIED", "PENDING_REVALIDATION"]:
            is_golden_record_candidate = False
            # As razões já devem ter sido adicionadas no loop acima
        else:
            actions_summary["is_golden_record_candidate"] = is_golden_record_candidate
            actions_summary["reason"].extend(golden_record_reasons)


        # Step 3: Tomar decisão final sobre o ValidationRecord
        # A ordem das condições aqui é crucial para determinar o status final.
        if record_needs_revalidation:
            # Se precisa de revalidação, adiciona à fila de pendentes
            record.is_golden_record = False # Não é um Golden Record ainda
            record.status_qualificacao = "PENDING_REVALIDATION"
            actions_summary["status_qualificacao_set"] = "PENDING_REVALIDATION"
            actions_summary["moved_to_qualificacoes_pendentes_queue"] = True
            
            # Recupera o contador de tentativas se o registro já existe na fila (para calcular backoff)
            existing_pending_rec = await self.qualification_repo.get_pending_qualification_by_validation_record_id(str(record.id))
            attempt_count = existing_pending_rec.attempt_count + 1 if existing_pending_rec else 0
            
            # 3. Estratégia de Revalidação (Backoff Exponencial)
            delay_days = 2 ** attempt_count # 1, 2, 4, 8... dias
            scheduled_next_attempt = datetime.now(timezone.utc) + timedelta(days=delay_days)

            try:
                pending_rec = QualificacaoPendente(
                    id=existing_pending_rec.id if existing_pending_rec else str(uuid.uuid4()), # Reusa ID ou gera novo
                    validation_record_id=str(record.id), # Converter UUID para str
                    client_identifier=record.client_identifier,
                    validation_type=record.tipo_validacao, # Tipo da validação composta 'pessoa_completa'
                    status_motivo=revalidation_reason,
                    attempt_count=attempt_count,
                    last_attempt_at=datetime.now(timezone.utc),
                    scheduled_next_attempt_at=scheduled_next_attempt
                )
                if existing_pending_rec:
                    await self.qualification_repo.update_pending_qualification(pending_rec.id, pending_rec.dict())
                    logger.info(f"Registro {record.id} existente na fila de pendentes atualizado. Próxima tentativa agendada para: {scheduled_next_attempt}.")
                else:
                    await self.qualification_repo.create_pending_qualification(pending_rec)
                    logger.info(f"Registro {record.id} marcado como PENDING_REVALIDATION e adicionado à fila de qualificações pendentes. Próxima tentativa agendada para: {scheduled_next_attempt}.")
            except Exception as e:
                logger.error(f"Falha ao criar/atualizar registro de qualificação pendente para {record.id}: {e}")
                actions_summary["moved_to_qualificacoes_pendentes_queue"] = False
                actions_summary["reason"].append(f"Erro ao adicionar à fila de revalidação: {e}")
                # Se falhar em adicionar à fila de revalidação, ele deve se tornar UNQUALIFIED
                record.is_golden_record = False
                record.status_qualificacao = "UNQUALIFIED"
                actions_summary["status_qualificacao_set"] = "UNQUALIFIED"

        elif is_golden_record_candidate:
            record.is_golden_record = True
            record.status_qualificacao = "QUALIFIED"
            actions_summary["status_qualificacao_set"] = "QUALIFIED"
            logger.info(f"Registro {record.id} é um candidato a Golden Record e QUALIFICADO.")

            # Tenta criar/atualizar o Client Entity (Golden Record no mestre)
            cpf_validation = individual_validations.get("cpf")
            main_document_normalized = cpf_validation.get("dado_normalizado") if cpf_validation and cpf_validation.get("is_valid") else None

            if main_document_normalized:
                try:
                    client_entity = await self.qualification_repo.get_client_entity_by_main_document(main_document_normalized)
                    consolidated_data = self._consolidate_golden_record_data(record)

                    # 6. golden_record_ids_to_link Dinâmico: Otimizado
                    golden_record_ids_to_link = self._get_golden_record_link_ids(record, individual_validations)
                    
                    # 5. relationship_type e cclub Dinâmicos: Usando app_info
                    relationship_type = app_info.get("relationship_type", "Pessoa Fisica") # Default se não fornecido
                    cclub_identifier = app_info.get("cclub_identifier", record.client_identifier) # Default se não fornecido

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
                            logger.error(f"Falha ao atualizar Golden Record existente para {main_document_normalized}. "
                                         f"Registro {record.id} não terá link para GR atualizado.")
                            # 1. Tratamento de Erros: Reverte status se falha na atualização do GR
                            record.is_golden_record = False
                            record.status_qualificacao = "UNQUALIFIED"
                            actions_summary["status_qualificacao_set"] = "UNQUALIFIED"
                            actions_summary["reason"].append("Falha ao atualizar Golden Record existente.")
                    else:
                        # Cria um novo Golden Record
                        new_entity_data = {
                            "main_document_normalized": main_document_normalized,
                            "consolidated_data": consolidated_data,
                            "relationship_type": relationship_type, 
                            "cclub": cclub_identifier, 
                            **golden_record_ids_to_link
                        }
                        new_entity = await self.qualification_repo.create_client_entity(new_entity_data)
                        if new_entity:
                            record.golden_record_id = new_entity["id"] # Linka o validation_record ao GR
                            actions_summary["client_entity_created_or_updated"] = True
                            logger.info(f"Novo Golden Record criado para cliente {main_document_normalized}. ID: {new_entity['id']}")
                        else:
                            logger.error(f"Falha ao criar novo Golden Record para {main_document_normalized}. "
                                         f"Registro {record.id} não será um GR.")
                            # 1. Tratamento de Erros: Reverte status se falha na criação do GR
                            record.is_golden_record = False
                            record.status_qualificacao = "UNQUALIFIED"
                            actions_summary["status_qualificacao_set"] = "UNQUALIFIED"
                            actions_summary["reason"].append("Falha ao criar novo Golden Record.")
                except Exception as e:
                    logger.error(f"Exceção inesperada ao manipular Golden Record para {main_document_normalized}: {e}")
                    record.is_golden_record = False
                    record.status_qualificacao = "UNQUALIFIED"
                    actions_summary["status_qualificacao_set"] = "UNQUALIFIED"
                    actions_summary["reason"].append(f"Erro ao criar/atualizar Golden Record: {e}")
            else:
                logger.warning(f"Não foi possível determinar o documento principal normalizado para criar/atualizar o Golden Record para o registro {record.id}. O registro não será um GR na tabela de entidades de cliente.")
                record.is_golden_record = False # Se não tem documento principal, não pode ser GR
                record.status_qualificacao = "UNQUALIFIED"
                actions_summary["status_qualificacao_set"] = "UNQUALIFIED"


        else:
            # Não é Golden Record e não vai para pendente (inválido ou inconsistente)
            record.is_golden_record = False
            record.status_qualificacao = "UNQUALIFIED"
            actions_summary["status_qualificacao_set"] = "UNQUALIFIED"
            logger.info(f"Registro {record.id} marcado como UNQUALIFIED.")
            
        # Salva as atualizações no ValidationRecord (is_golden_record, status_qualificacao, golden_record_id)
        try:
            await self.validation_repo.update_record(record.id, {
                "is_golden_record": record.is_golden_record,
                "status_qualificacao": record.status_qualificacao,
                "golden_record_id": record.golden_record_id,
                "last_enrichment_attempt_at": datetime.now(timezone.utc) if record.is_golden_record else None # Adiciona timestamp
            })
            logger.info(f"ValidationRecord {record.id} atualizado com status {record.status_qualificacao}.")
        except Exception as e:
            logger.error(f"Falha ao atualizar ValidationRecord {record.id} no banco de dados: {e}")
            actions_summary["reason"].append(f"Falha ao salvar status final no ValidationRecord: {e}")

        return actions_summary

    async def _evaluate_golden_record_candidacy(self, record: ValidationRecord) -> (bool, List[str]):
        logger.debug(f"Avaliando candidatura a Golden Record para registro {record.id}. Detalhes de validação: {record.validation_details}")
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

        for field, required_rule in self.CRITICAL_GOLDEN_RECORD_RULES.items():
            val_detail = individual_validations.get(field)
            
            if not val_detail or not val_detail.get("is_valid"):
                critical_fields_valid = False
                msg = val_detail.get('mensagem', 'Inválido') if val_detail else "Não fornecido ou formato incorreto."
                reasons.append(f"{field.capitalize()}: {msg}. Detalhes: {val_detail}")
                continue
            
            # Se uma regra específica é exigida, verifica se ela foi aplicada
            if required_rule and val_detail.get("business_rule_applied", {}).get("code") != required_rule:
                critical_fields_valid = False
                msg = val_detail.get('mensagem', 'Não atende regra específica.')
                reasons.append(f"{field.capitalize()}: {msg} ou não atende a regra de negócio {required_rule}. Detalhes: {val_detail}")
        
        # Lógica para o telefone fixo, que pode ter sido RN_TEL004 e não está na lista CRITICAL_GOLDEN_RECORD_RULES
        # Se ele foi identificado como needing revalidation (RN_TEL004), não pode ser um Golden Record inicial.
        telefone_fixo_validation = individual_validations.get("telefone_fixo")
        if telefone_fixo_validation and telefone_fixo_validation.get("business_rule_applied", {}).get("code") in self.REVALIDATION_PHONE_RULES:
            critical_fields_valid = False
            reasons.append("Telefone Fixo: Necessita revalidação (RN_TEL004), impedindo candidatura a Golden Record inicial.")

        logger.info(f"Avaliação Golden Record para {record.id}: Candidato={critical_fields_valid}, Razões: {reasons}")
        return critical_fields_valid, reasons
    
    # 6. golden_record_ids_to_link Dinâmico: Otimizado
    def _get_golden_record_link_ids(self, record: ValidationRecord, individual_validations: Dict[str, Any]) -> Dict[str, str]:
        """
        Gera um dicionário de IDs de Golden Record para vincular ao ClientEntity,
        baseado nas validações individuais e nas regras de negócio aplicadas.
        """
        golden_record_ids = {}
        # Mapeamento de campos para os nomes de chave no ClientEntity
        field_to_gr_id_map = {
            "cpf": "golden_record_cpf_cnpj_id",
            "endereco": "golden_record_address_id",
            "celular": "golden_record_phone_id",
            "email": "golden_record_email_id",
            "cep": "golden_record_cep_id",
            "rg": "golden_record_rg_id",
            "telefone_fixo": "golden_record_phone_id", # Reusa o mesmo ID de telefone
        }

        for field, gr_id_key in field_to_gr_id_map.items():
            val_detail = individual_validations.get(field)
            if val_detail and val_detail.get("is_valid"):
                # Verifica se a regra de negócio para GR foi aplicada com sucesso
                required_rule = self.CRITICAL_GOLDEN_RECORD_RULES.get(field)
                
                # Exceção para telefone fixo: RN_TEL004 não deve gerar um GR ID aqui, pois indica revalidação
                if field == "telefone_fixo" and val_detail.get("business_rule_applied", {}).get("code") in self.REVALIDATION_PHONE_RULES:
                    continue # Não gera GR ID se é para revalidação
                
                if required_rule is None or val_detail.get("business_rule_applied", {}).get("code") == required_rule:
                    golden_record_ids[gr_id_key] = str(record.id)
                
            # Tratamento especial para CEP se estiver aninhado no endereço, mas a regra for VAL_CEP001
            if field == "endereco":
                cep_val_from_address = val_detail.get("details", {}).get("cep_validation_result", {}) # Mudança de 'cep_validation' para 'cep_validation_result'
                if cep_val_from_address and cep_val_from_address.get("is_valid") and \
                   cep_val_from_address.get("business_rule_applied", {}).get("code") == self.CRITICAL_GOLDEN_RECORD_RULES.get("cep"):
                    golden_record_ids["golden_record_cep_id"] = str(record.id)

        return golden_record_ids

    # 4. Flexibilidade na Consolidação de Dados: Otimizado
    def _consolidate_golden_record_data(self, record: ValidationRecord) -> Dict[str, Any]:
        """
        Consolida os dados normalizados das validações individuais para o Golden Record.
        Prioriza dados de sub-validações válidas que atenderam às regras de Golden Record.
        """
        consolidated_data = {}
        individual_validations = record.validation_details.get("individual_validations", {})

        # Campos diretos da validação composta que podem ser incluídos se válidos
        for field, required_rule in self.CRITICAL_GOLDEN_RECORD_RULES.items():
            val_detail = individual_validations.get(field)
            if val_detail and val_detail.get("is_valid"):
                if required_rule is None or val_detail.get("business_rule_applied", {}).get("code") == required_rule:
                    # Usa o dado normalizado ou o dado original se não houver normalização
                    consolidated_data[field] = val_detail.get("dado_normalizado", val_detail.get("dado_original"))
            
            # Se o campo é 'endereco', verifica se há validação de CEP dentro dele
            if field == "endereco":
                cep_val_from_address = val_detail.get("details", {}).get("cep_validation_result", {}) # Mudança de 'cep_validation' para 'cep_validation_result'
                if cep_val_from_address and cep_val_from_address.get("is_valid") and \
                   cep_val_from_address.get("business_rule_applied", {}).get("code") == self.CRITICAL_GOLDEN_RECORD_RULES.get("cep"):
                    consolidated_data["cep"] = cep_val_from_address.get("dado_normalizado", cep_val_from_address.get("dado_original"))

        # Adiciona o telefone fixo se for válido (RN_TEL001), mas *não* se for RN_TEL004
        telefone_fixo_val = individual_validations.get("telefone_fixo")
        if telefone_fixo_val and telefone_fixo_val.get("is_valid") and \
           telefone_fixo_val.get("business_rule_applied", {}).get("code") == "RN_TEL001":
            consolidated_data["telefone_fixo"] = telefone_fixo_val.get("dado_normalizado", telefone_fixo_val.get("dado_original"))


        # Renomeia 'cpf' para 'cpf_cnpj' se necessário e garante que 'nome' e 'sexo' estejam presentes
        if "cpf" in consolidated_data:
            consolidated_data["cpf_cnpj"] = consolidated_data.pop("cpf")
        
        # Incluir nome e sexo normalizados, mesmo que não tenham uma regra específica no CRITICAL_GOLDEN_RECORD_RULES
        # (já que a validação de Golden Record os verifica apenas por 'is_valid')
        nome_val = individual_validations.get("nome")
        if nome_val and nome_val.get("is_valid"):
            consolidated_data["nome"] = nome_val.get("dado_normalizado", nome_val.get("dado_original"))
        
        sexo_val = individual_validations.get("sexo")
        if sexo_val and sexo_val.get("is_valid"):
            consolidated_data["sexo"] = sexo_val.get("dado_normalizado", sexo_val.get("dado_original"))

        data_nascimento_val = individual_validations.get("data_nascimento")
        if data_nascimento_val and data_nascimento_val.get("is_valid"):
            consolidated_data["data_nascimento"] = data_nascimento_val.get("dado_normalizado", data_nascimento_val.get("dado_original"))

        # Remove valores None
        return {k: v for k, v in consolidated_data.items() if v is not None}