# app/services/validation_service.py
import logging
import json
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timezone
import hashlib # Importa hashlib para gerar hash SHA256

# Importações internas do projeto
from app.auth.api_key_manager import APIKeyManager
from app.database.repositories import ValidationRecordRepository
from app.rules.decision_rules import DecisionRules
from app.models.validation_record import ValidationRecord
from app.models.validation_request import ValidationRequest
from app.models.golden_record_summary import GoldenRecordSummary

# Importar validadores específicos (Injeção de Dependência)
from app.rules.phone.validator import PhoneValidator
from app.rules.address.cep.validator import CEPValidator
from app.rules.email.validator import EmailValidator
from app.rules.document.cpf_cnpj.validator import CpfCnpjValidator
from app.rules.address.address_validator import AddressValidator 

logger = logging.getLogger(__name__)

# --- Constantes de Mensagens ---
API_KEY_INVALID_MESSAGE = "API Key inválida."
VALIDATION_SERVICE_NOT_READY_MESSAGE = "Serviço de validação não está pronto. Tente novamente mais tarde."
INTERNAL_SERVER_ERROR_MESSAGE = "Erro interno no servidor ao processar a validação."
VALIDATION_ERROR_MESSAGE = "Erro de validação de entrada ou funcionalidade não implementada."

class ValidationService:
    """
    Serviço centralizado para autenticação, validação de dados e gestão de registros.
    Orquestra a chamada aos validadores específicos, persistência, aplicação de regras de negócio
    e gestão do Golden Record.
    """

    def __init__(
        self,
        api_key_manager: APIKeyManager,
        repo: ValidationRecordRepository,
        decision_rules: DecisionRules,
        phone_validator: PhoneValidator,
        cep_validator: CEPValidator,
        email_validator: EmailValidator,
        cpf_cnpj_validator: CpfCnpjValidator,
    ):
        self.api_key_manager = api_key_manager
        self.repo = repo
        self.decision_rules = decision_rules

        # Atribuição dos validadores injetados
        self.phone_validator = phone_validator
        self.cep_validator = cep_validator
        self.email_validator = email_validator
        self.cpf_cnpj_validator = cpf_cnpj_validator

        address_validator_instance = AddressValidator(cep_validator=cep_validator)

        self.validators: Dict[str, Any] = {
            "telefone": self.phone_validator, 
            "cep": self.cep_validator,       
            "email": self.email_validator,   
            "cpf_cnpj": self.cpf_cnpj_validator, 
            "endereco": address_validator_instance, 
        }
        logger.info("ValidationService inicializado com sucesso.")

    async def _get_validator(self, validation_type: str) -> Any:
        """
        Retorna a instância do validador para o tipo de validação especificada.
        Levanta um ValueError se o tipo não for suportado.
        """
        validator = self.validators.get(validation_type)
        if not validator:
            logger.error(f"Tipo de validação '{validation_type}' não suportado ou validador não configurado.")
            raise ValueError(f"Tipo de validação '{validation_type}' não suportado ou validador não configurado.")
        return validator

    async def _perform_data_validation(self, validation_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa a validação específica do tipo de dado e retorna o resultado.
        """
        validator = await self._get_validator(validation_type)
        input_data_original = ""
        primary_validation_result: Dict[str, Any] = {}

        if validation_type == "telefone":
            phone_number = data.get("phone_number")
            country_hint = data.get("country_hint")
            if not phone_number:
                raise ValueError("Para validação de 'telefone', o campo 'phone_number' é obrigatório em 'data'.")
            input_data_original = phone_number
            primary_validation_result = await validator.validate(phone_number, country_hint=country_hint) 
        elif validation_type == "cep":
            cep_number = data.get("cep")
            if not cep_number:
                raise ValueError("Para validação de 'cep', o campo 'cep' é obrigatório em 'data'.")
            input_data_original = cep_number
            primary_validation_result = await validator.validate(cep_number) 
        elif validation_type == "email":
            email_address = data.get("email_address")
            if not email_address:
                raise ValueError("Para validação de 'email', o campo 'email_address' é obrigatório em 'data'.")
            input_data_original = email_address
            primary_validation_result = await validator.validate(email_address) 
        elif validation_type == "cpf_cnpj":
            document_number = data.get("document_number")
            if not document_number:
                raise ValueError("Para validação de 'cpf_cnpj', o campo 'document_number' é obrigatório em 'data'.")
            input_data_original = document_number
            primary_validation_result = await validator.validate(document_number) 
        elif validation_type == "endereco":
            address_data = {
                "logradouro": data.get("logradouro"),
                "numero": data.get("numero"),
                "complemento": data.get("complemento"),
                "bairro": data.get("bairro"),
                "cidade": data.get("cidade"),
                "estado": data.get("estado"),
                "cep": data.get("cep") 
            }
            address_data_cleaned = {k: v for k, v in address_data.items() if v is not None}
            if not address_data_cleaned:
                raise ValueError("Para validação de 'endereco', ao menos um campo de endereço (logradouro, numero, etc.) é obrigatório em 'data'.")
            
            input_data_original = ", ".join([f"{k}: {v}" for k, v in address_data_cleaned.items()])
            primary_validation_result = await validator.validate(address_data_cleaned) 
        else:
            raise NotImplementedError(f"Validação para o tipo '{validation_type}' não implementada ou configurada neste serviço.")

        primary_validation_result["input_data_original"] = input_data_original
        return primary_validation_result

    def _create_initial_validation_record_model(self,
                                                 primary_validation_result: Dict[str, Any],
                                                 request: ValidationRequest,
                                                 app_name: str) -> ValidationRecord:
        """
        Cria e retorna uma instância inicial de ValidationRecord com os resultados da validação primária.
        Gera o 'client_entity_id' com base no client_identifier, dado normalizado e um identificador adicional (cclub ou cpssoa).
        """
        current_user_identifier = request.operator_id if request.operator_id else app_name

        business_rule_params_from_validation = primary_validation_result.get("business_rule_applied", {}).get("parameters", {})

        # Lógica para gerar o client_entity_id
        # Prioriza 'cclub', depois 'cpssoa'. Se nenhum for encontrado, usa string vazia.
        additional_identifier = ""
        if "cclub" in request.data and request.data["cclub"]:
            additional_identifier = str(request.data["cclub"])
        elif "cpssoa" in request.data and request.data["cpssoa"]:
            additional_identifier = str(request.data["cpssoa"])
        # Nota: 'cpf' como campo distinto em request.data só seria necessário se fosse um CPF diferente do dado_normalizado
        # Caso contrário, o dado_normalizado já o incluirá.

        identification_parts = [
            request.client_identifier,
            request.validation_type,
            primary_validation_result.get("dado_normalizado", ""),
            additional_identifier
        ]
        # Filtra partes vazias ou None para evitar "-NONE-" no hash
        composite_id_string = "-".join(filter(None, identification_parts)) 
        client_entity_id_generated = hashlib.sha256(composite_id_string.encode('utf-8')).hexdigest()

        record_model = ValidationRecord(
            dado_original=primary_validation_result.get("input_data_original", ""),
            dado_normalizado=primary_validation_result.get("dado_normalizado"),
            is_valido=primary_validation_result.get("is_valid", False),
            mensagem=primary_validation_result.get("mensagem", "Validação concluída."),
            origem_validacao=primary_validation_result.get("origem_validacao", "servico_generico"),
            tipo_validacao=request.validation_type,
            app_name=app_name,
            client_identifier=request.client_identifier,
            client_entity_id=client_entity_id_generated, # Campo agora gerado internamente
            validation_details=primary_validation_result.get("details", {}),
            data_validacao=datetime.now(timezone.utc), 

            regra_negocio_codigo=primary_validation_result.get("business_rule_applied", {}).get("code"),
            regra_negocio_descricao=primary_validation_result.get("business_rule_applied", {}).get("description"),
            regra_negocio_tipo=primary_validation_result.get("business_rule_applied", {}).get("type"),
            regra_negocio_parametros=business_rule_params_from_validation, 

            usuario_criacao=current_user_identifier, 
            usuario_atualizacao=current_user_identifier,
            is_deleted=False,
            deleted_at=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return record_model

    async def _apply_business_rules_to_record(self, record_model: ValidationRecord, app_info: Dict[str, Any]) -> None:
        """
        Aplica as regras de decisão de negócio pós-validação e atualiza o registro in-place.
        As regras de decisão podem alterar o 'is_valido', 'mensagem', e os detalhes da regra de negócio.
        """
        actions_summary = await self.decision_rules.apply_post_validation_actions(record_model, app_info)
        
        if record_model.validation_details is None:
            record_model.validation_details = {}
        
        record_model.validation_details["post_validation_actions_summary"] = actions_summary

        business_rule_details_from_decision = record_model.validation_details.get("business_rule_applied", {})
        
        if business_rule_details_from_decision and \
           business_rule_details_from_decision.get("result") in ["Reprovado pela Regra de Negócio", "Não Aprovado pela Regra de Negócio"]:
            
            record_model.is_valido = False
            record_model.mensagem = business_rule_details_from_decision.get("description", "Reprovado por regra de negócio.")
            record_model.regra_negocio_codigo = business_rule_details_from_decision.get("code", record_model.regra_negocio_codigo)
            record_model.regra_negocio_descricao = business_rule_details_from_decision.get("description", record_model.regra_negocio_descricao)
            record_model.regra_negocio_tipo = business_rule_details_from_decision.get("type", record_model.regra_negocio_tipo)
            record_model.regra_negocio_parametros = record_model.regra_negocio_parametros 
            logger.info(f"Regra de negócio '{record_model.regra_negocio_codigo}' reprovou o dado. is_valido definido como False.")
        else:
            if business_rule_details_from_decision:
                record_model.regra_negocio_codigo = business_rule_details_from_decision.get("code", record_model.regra_negocio_codigo)
                record_model.regra_negocio_descricao = business_rule_details_from_decision.get("description", record_model.regra_negocio_descricao)
                record_model.regra_negocio_tipo = business_rule_details_from_decision.get("type", record_model.regra_negocio_tipo)
                record_model.regra_negocio_parametros = record_model.regra_negocio_parametros


    async def _handle_golden_record_logic(self,
                                          current_record_model: ValidationRecord,
                                          normalized_data: Optional[str],
                                          validation_type: str) -> Tuple[ValidationRecord, bool, Optional[int], Optional[GoldenRecordSummary]]:
        """
        Gerencia a lógica de Golden Record: busca, persiste, elege e atualiza status.
        Retorna o registro persistido, se é o GR, o ID do GR e os dados do GR.
        """
        if not normalized_data:
            current_record_model.is_golden_record = False
            current_record_model.golden_record_id = None
            final_record = await self.repo.create_record(current_record_model)
            if not final_record:
                raise Exception("Falha ao criar registro para dado não normalizado.")
            logger.info(f"Registro criado sem dado normalizado (ID: {final_record.id}). Não elegível para Golden Record.")
            return final_record, False, None, None

        existing_records = await self.repo.get_all_records_by_normalized_data(
            dado_normalizado=normalized_data,
            tipo_validacao=validation_type,
            include_deleted=False 
        )
        logger.debug(f"Encontrados {len(existing_records)} registros existentes para '{normalized_data}'.")

        final_persisted_record = await self._persist_current_record(current_record_model, existing_records)
        if not final_persisted_record:
            raise Exception("Falha ao persistir o registro atual.")
        
        records_to_evaluate = [rec for rec in existing_records if rec.id != final_persisted_record.id]
        records_to_evaluate.append(final_persisted_record)
        
        candidate_golden_record, best_score = self._elect_golden_record_candidate(records_to_evaluate)
        
        golden_record_id = candidate_golden_record.id if candidate_golden_record else None
        is_this_transaction_golden_record = (candidate_golden_record and candidate_golden_record.id == final_persisted_record.id)

        if candidate_golden_record:
            await self._update_database_golden_record_statuses(
                normalized_data, validation_type, golden_record_id, records_to_evaluate
            )
            logger.info(f"Registro ID {candidate_golden_record.id} eleito como o novo Golden Record para '{normalized_data}' (score: {best_score}).")
        else:
            logger.warning(f"Nenhum Golden Record eleito para '{normalized_data}'. Isso pode ocorrer se não houver registros válidos.")

        final_persisted_record_reloaded = await self.repo.get_record_by_id(final_persisted_record.id)
        if not final_persisted_record_reloaded:
            logger.error(f"Falha crítica ao recarregar o registro final {final_persisted_record.id} após lógica de GR. Usando versão em memória.")
            final_persisted_record_reloaded = final_persisted_record 

        golden_record_for_response = await self._get_golden_record_summary_for_response(golden_record_id)

        return final_persisted_record_reloaded, is_this_transaction_golden_record, golden_record_id, golden_record_for_response

    async def _persist_current_record(self, current_record_model: ValidationRecord, existing_records: List[ValidationRecord]) -> Optional[ValidationRecord]:
        """
        Persiste o registro atual no banco de dados (cria ou atualiza).
        Prioriza a atualização se já existe um registro da mesma aplicação para o dado normalizado.
        """
        existing_record_for_current_app: Optional[ValidationRecord] = next(
            (rec for rec in existing_records if rec.app_name == current_record_model.app_name),
            None
        )

        if existing_record_for_current_app:
            current_record_model.id = existing_record_for_current_app.id 
            current_record_model.updated_at = datetime.now(timezone.utc) 
            final_persisted_record = await self.repo.update_record(existing_record_for_current_app.id, current_record_model)
            if not final_persisted_record:
                logger.error(f"Falha ao atualizar registro {existing_record_for_current_app.id}. Retornando o registro existente em memória.")
                final_persisted_record = existing_record_for_current_app 
            logger.info(f"Registro existente para '{current_record_model.app_name}' ('{current_record_model.dado_normalizado}') atualizado. ID: {final_persisted_record.id}")
        else:
            final_persisted_record = await self.repo.create_record(current_record_model)
            if not final_persisted_record:
                logger.error("Falha ao criar novo registro.")
                return None 
            logger.info(f"Novo registro criado para '{current_record_model.app_name}' ('{current_record_model.dado_normalizado}'). ID: {final_persisted_record.id}")
        return final_persisted_record


    def _elect_golden_record_candidate(self, records_to_evaluate: List[ValidationRecord]) -> Tuple[Optional[ValidationRecord], int]:
        """
        Elege o melhor candidato a Golden Record a partir de uma lista de registros válidos.
        Prioriza registros com maior pontuação e, em caso de empate, o mais recente.
        """
        best_score = -1
        candidate_golden_record: Optional[ValidationRecord] = None

        valid_records = [rec for rec in records_to_evaluate if rec.is_valido]

        if not valid_records:
            logger.info("Nenhum registro válido encontrado para eleição do Golden Record.")
            return None, -1

        for rec in valid_records:
            score = self._score_record(rec) 
            if score > best_score or (score == best_score and candidate_golden_record and rec.data_validacao and rec.data_validacao > candidate_golden_record.data_validacao):
                best_score = score
                candidate_golden_record = rec
        
        logger.debug(f"Golden Record candidato eleito: ID={candidate_golden_record.id if candidate_golden_record else 'N/A'}, Score={best_score}")
        return candidate_golden_record, best_score

    def _score_record(self, record: ValidationRecord) -> int:
        """
        Atribui uma pontuação a um registro de validação para a eleição do Golden Record.
        Regras de pontuação:
        - Registros válidos: +1000 pontos (alta prioridade)
        - Pontuação por confiabilidade da fonte (app_name):
            - CRM_Principal: +500
            - ERP_System: +450
            - Seguros App: +300
            - App_Marketing: +100
            - Outros: +50
        - Pontuação por detalhes de validação (exemplos):
            - Telefone validado por lib externa (phonenumbers): +50
            - CEP com endereço completo encontrado: +50
            - Email com sintaxe válida: +40
            - Email com domínio resolúvel: +60
            - CPF/CNPJ com checksum válido: +70
            - CPF/CNPJ com status 'REGULAR' da Receita Federal: +100
            - Endereço normalizado: +40
            - Endereço geocodificado: +80
        - Recência: Pequeno bônus baseado no timestamp (desempate).
        """
        score = 0
        
        # Prioridade 1: Validade do Dado (muito importante)
        if record.is_valido:
            score += 1000 

        # Prioridade 2: Confiabilidade da Fonte (app_name)
        if record.app_name == "CRM_Principal":
            score += 500
        elif record.app_name == "ERP_System":
            score += 450
        elif record.app_name == "Seguros App":
            score += 300
        elif record.app_name == "App_Marketing":
            score += 100
        else:
            score += 50 # Outras aplicações genéricas

        # Prioridade 3: Integridade/Detalhes da Validação (baseado nos validation_details)
        if record.validation_details:
            if record.tipo_validacao == "telefone":
                if record.validation_details.get("phonenumbers_valid"):
                    score += 50 # Telefone validado pela biblioteca é mais confiável
            elif record.tipo_validacao == "cep":
                if record.validation_details.get("address_found"):
                    score += 50 # CEP que encontrou um endereço completo é melhor
            elif record.tipo_validacao == "email":
                if record.validation_details.get("is_syntax_valid"):
                    score += 40 # Email com sintaxe válida
                if record.validation_details.get("domain_resolves"):
                    score += 60 # Email com domínio resolúvel é mais confiável
            elif record.tipo_validacao == "cpf_cnpj":
                if record.validation_details.get("is_valid_checksum"):
                    score += 70 # CPF/CNPJ com checksum válido
                if record.validation_details.get("status_receita_federal") == "REGULAR":
                    score += 100 # CPF/CNPJ com status regular na Receita é excelente
            elif record.tipo_validacao == "endereco":
                if record.validation_details.get("is_normalized"):
                    score += 40 # Endereço normalizado
                if record.validation_details.get("is_geocoded"):
                    score += 80 # Endereço geocodificado é de alta qualidade

        # Prioridade 4: Recência (pequeno bônus por data, para desempate)
        if record.data_validacao:
            now = datetime.now(timezone.utc)
            time_diff_seconds = (now - record.data_validacao).total_seconds()
            
            # Bônus para registros mais recentes (ex: 1 ponto por dia no último ano, max 365)
            max_recency_seconds = 365 * 24 * 3600 # Um ano em segundos
            recency_bonus = max(0, int((max_recency_seconds - time_diff_seconds) / (86400 * 5))) # 1 ponto a cada 5 dias
            score += recency_bonus
        
        return score


    async def _update_database_golden_record_statuses(self, normalized_data: str, validation_type: str, golden_record_id: Optional[int], records_to_evaluate: List[ValidationRecord]):
        """
        Atualiza o status de Golden Record no banco de dados para todos os registros afetados.
        """
        if not golden_record_id:
            logger.warning(f"Tentativa de atualizar status do Golden Record sem um golden_record_id válido para '{normalized_data}'. Ignorando.")
            return

        all_related_records = await self.repo.get_all_records_by_normalized_data(
            dado_normalizado=normalized_data,
            tipo_validacao=validation_type,
            include_deleted=True 
        )

        for rec in all_related_records:
            if rec.id == golden_record_id:
                if not rec.is_golden_record or rec.golden_record_id != golden_record_id:
                    logger.debug(f"Atualizando GR status: Record ID {rec.id} para True, Golden Record ID {golden_record_id}.")
                    await self.repo.update_golden_record_status(
                        rec.id,
                        is_golden=True,
                        golden_record_id=golden_record_id 
                    )
            else:
                if rec.is_golden_record or rec.golden_record_id != golden_record_id:
                    logger.debug(f"Atualizando GR status: Record ID {rec.id} para False, Golden Record ID {golden_record_id}.")
                    await self.repo.update_golden_record_status(
                        rec.id,
                        is_golden=False,
                        golden_record_id=golden_record_id
                    )
        logger.info(f"Status de Golden Record atualizados no DB para dado normalizado '{normalized_data}'. Novo GR ID: {golden_record_id}.")


    async def _get_golden_record_summary_for_response(self, golden_record_id: Optional[int]) -> Optional[GoldenRecordSummary]:
        """
        Busca o Golden Record completo e prepara o resumo para a resposta da API.
        """
        if golden_record_id:
            full_golden_record = await self.repo.get_record_by_id(golden_record_id)
            if full_golden_record:
                return GoldenRecordSummary(
                    id=full_golden_record.id,
                    dado_original=full_golden_record.dado_original,
                    dado_normalizado=full_golden_record.dado_normalizado,
                    is_valido=full_golden_record.is_valido,
                    app_name=full_golden_record.app_name,
                    data_validacao=full_golden_record.data_validacao
                )
        return None

    async def validate_data(self, api_key_str: str, request: ValidationRequest) -> Dict[str, Any]:
        """
        Processa uma requisição de validação de dados: autentica, valida, persiste,
        aplica regras de negócio e gerencia o Golden Record.
        """
        logger.info(f"Recebida requisição para validar tipo '{request.validation_type}'. ID do Cliente: {request.client_identifier}. Operador: {request.operator_id}")

        app_info = self.api_key_manager.get_app_info(api_key_str)
        if not app_info:
            logger.warning(f"Tentativa de acesso com API Key inválida: {api_key_str[:5]}...")
            return {"status": "error", "message": API_KEY_INVALID_MESSAGE, "code": 401, "is_valid": False}

        app_name = app_info.get("app_name", "Desconhecido")
        logger.info(f"API Key '{app_name}' autenticada. Proseguindo com validação de {request.validation_type}.")

        input_data_original = "" 
        final_persisted_record: Optional[ValidationRecord] = None 

        try:
            primary_validation_result = await self._perform_data_validation(request.validation_type, request.data)
            input_data_original = primary_validation_result.get("input_data_original", "")

            current_record_model = self._create_initial_validation_record_model(
                primary_validation_result, request, app_name
            )

            await self._apply_business_rules_to_record(current_record_model, app_info)

            final_persisted_record, is_this_transaction_golden_record, golden_record_id, golden_record_data = \
                await self._handle_golden_record_logic(
                    current_record_model,
                    current_record_model.dado_normalizado, 
                    request.validation_type
                )

            logger.info(f"Operação de validação e Golden Record concluída para ID {final_persisted_record.id if final_persisted_record else 'N/A'}. "
                        f"Válido: {final_persisted_record.is_valido if final_persisted_record else 'N/A'}. "
                        f"Este registro é GR: {is_this_transaction_golden_record}. ID do GR: {golden_record_id}")

            return self._build_response_payload(
                final_persisted_record,
                is_this_transaction_golden_record,
                golden_record_id,
                golden_record_data
            )

        except (ValueError, NotImplementedError) as e:
            logger.error(f"{VALIDATION_ERROR_MESSAGE}: {e}", exc_info=True)
            code = 400 if isinstance(e, ValueError) else 501
            return {
                "status": "error",
                "message": str(e),
                "code": code,
                "is_valid": False,
                "validation_details": {"error_type": "input_validation_or_not_implemented_error"}
            }
        except Exception as e:
            logger.error(f"Erro inesperado durante o processamento da validação para '{input_data_original}': {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"{INTERNAL_SERVER_ERROR_MESSAGE}: {e}",
                "code": 500,
                "is_valid": False,
                "validation_details": {"error_type": "internal_server_error"}
            }

    def _build_response_payload(
        self,
        record: ValidationRecord,
        is_this_transaction_golden_record: bool,
        golden_record_id: Optional[int],
        golden_record_data: Optional[GoldenRecordSummary]
    ) -> Dict[str, Any]:
        """Constrói o payload da resposta da API."""
        return {
            "status": "success" if record.is_valido else "invalid",
            "message": record.mensagem,
            "is_valid": record.is_valido,
            "validation_details": record.validation_details,
            "app_name": record.app_name,
            "client_identifier": record.client_identifier,
            "record_id": record.id,
            "input_data_original": record.dado_original,
            "input_data_cleaned": record.dado_normalizado,
            "tipo_validacao": record.tipo_validacao,
            "origem_validacao": record.origem_validacao,
            "regra_negocio_codigo": record.regra_negocio_codigo,
            "regra_negocio_descricao": record.regra_negocio_descricao,
            "regra_negocio_tipo": record.regra_negocio_tipo,
            "regra_negocio_parametros": record.regra_negocio_parametros,
            "usuario_criacao": record.usuario_criacao,
            "usuario_atualizacao": record.usuario_atualizacao,
            "code": 200 if record.is_valido else 400,
            "is_golden_record_for_this_transaction": is_this_transaction_golden_record,
            "golden_record_id_for_normalized_data": golden_record_id,
            "golden_record_data": golden_record_data.model_dump(exclude_none=True) if golden_record_data else None,
            "client_entity_id": record.client_entity_id, 
            "status_qualificacao": record.status_qualificacao, 
            "last_enrichment_attempt_at": record.last_enrichment_attempt_at 
        }

    async def get_validation_history(self, api_key: str, limit: int = 10, include_deleted: bool = False) -> Dict[str, Any]:
        """
        Retorna o histórico de registros de validação para a aplicação autenticada.
        """
        logger.info(f"Recebida requisição de histórico para API Key: {api_key[:5]}..., Limite: {limit}, Incluir Deletados: {include_deleted}")
        app_info = self.api_key_manager.get_app_info(api_key)

        if not app_info:
            logger.warning(f"Tentativa de acesso não autorizado ao histórico com API Key inválida: {api_key[:5]}...")
            return {"status": "error", "message": API_KEY_INVALID_MESSAGE, "code": 401, "data": []}

        app_name = app_info.get("app_name", "Desconhecido")
        logger.info(f"API Key '{app_name}' autenticada para consulta de histórico.")

        try:
            records: List[ValidationRecord] = await self.repo.get_last_records(limit=limit, include_deleted=include_deleted)
            logger.info(f"Últimos {len(records)} registros de histórico recuperados (incluindo deletados: {include_deleted}).")

            history_data = []
            for rec in records:
                rec_dict = rec.model_dump(exclude_none=True)
                history_data.append(rec_dict)

            return {"status": "success", "data": history_data, "message": "Histórico obtido com sucesso.", "code": 200}
        except Exception as e:
            logger.error(f"Erro interno ao buscar histórico de validação: {e}", exc_info=True)
            return {"status": "error", "message": "Erro interno ao buscar histórico.", "code": 500, "data": []}

    async def soft_delete_record(self, api_key: str, record_id: int) -> Dict[str, Any]:
        """
        Executa o soft delete (exclusão lógica) de um registro de validação.
        Após o soft delete, reavalia e reelege o Golden Record para o dado normalizado, se necessário.
        """
        logger.info(f"Recebida requisição de soft delete para record_id: {record_id} pela API Key: {api_key[:5]}...")
        app_info = self.api_key_manager.get_app_info(api_key)

        if not app_info:
            logger.warning(f"Tentativa de soft delete com API Key inválida: {api_key[:5]}...")
            return {"status": "error", "message": API_KEY_INVALID_MESSAGE, "code": 401}

        try:
            record_to_delete = await self.repo.get_record_by_id(record_id)
            if not record_to_delete:
                logger.warning(f"Registro {record_id} não encontrado para soft delete.")
                return {"status": "failed", "message": f"Registro {record_id} não encontrado ou já deletado logicamente.", "code": 404}
            
            normalized_data = record_to_delete.dado_normalizado
            validation_type = record_to_delete.tipo_validacao
            was_golden_record = record_to_delete.is_golden_record

            success = await self.repo.soft_delete_record(record_id)
            if success:
                logger.info(f"Registro {record_id} soft-deletado com sucesso.")

                if normalized_data: 
                    if was_golden_record:
                        logger.info(f"Registro deletado ID {record_id} era o Golden Record. Reelegendo novo GR para '{normalized_data}'.")
                    else:
                        logger.info(f"Registro deletado ID {record_id} não era o Golden Record, mas ainda reavaliando para '{normalized_data}'.")
                    
                    remaining_records = await self.repo.get_all_records_by_normalized_data(
                        dado_normalizado=normalized_data,
                        tipo_validacao=validation_type,
                        include_deleted=False 
                    )
                    
                    new_golden_record_candidate, _ = self._elect_golden_record_candidate(remaining_records)
                    new_golden_record_id = new_golden_record_candidate.id if new_golden_record_candidate else None

                    await self._update_database_golden_record_statuses(
                        normalized_data, validation_type, new_golden_record_id, remaining_records
                    )
                    logger.info(f"Processo de reeleição do Golden Record concluído para '{normalized_data}'. Novo GR ID: {new_golden_record_id}.")

                return {"status": "success", "message": f"Registro {record_id} deletado logicamente com sucesso. Golden Record reavaliado.", "code": 200}
            else:
                logger.warning(f"Registro {record_id} não encontrado ou já deletado para soft delete.")
                return {"status": "failed", "message": f"Registro {record_id} não encontrado ou já está deletado logicamente.", "code": 404}
        except Exception as e:
            logger.error(f"Erro ao tentar soft-delete record {record_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno ao deletar registro: {e}", "code": 500}

    async def restore_record(self, api_key: str, record_id: int) -> Dict[str, Any]:
        """
        Restaura (remove o soft delete) de um registro de validação.
        Após a restauração, reavalia e reelege o Golden Record para o dado normalizado, se necessário.
        """
        logger.info(f"Recebida requisição de restauração para record_id: {record_id} pela API Key: {api_key[:5]}...")
        app_info = self.api_key_manager.get_app_info(api_key)

        if not app_info:
            logger.warning(f"Tentativa de restauração com API Key inválida: {api_key[:5]}...")
            return {"status": "error", "message": API_KEY_INVALID_MESSAGE, "code": 401}
        
        app_name = app_info.get("app_name", "Desconhecido")
        logger.info(f"API Key '{app_name}' autenticada para restauração.")

        try:
            record_to_restore = await self.repo.get_record_by_id(record_id, include_deleted=True) 
            if not record_to_restore or not record_to_restore.is_deleted:
                logger.warning(f"Registro {record_id} não encontrado ou não estava deletado para restauração.")
                return {"status": "failed", "message": f"Registro {record_id} não encontrado ou não estava deletado logicamente.", "code": 404}

            normalized_data = record_to_restore.dado_normalizado
            validation_type = record_to_restore.tipo_validacao

            success = await self.repo.restore_record(record_id)
            if success:
                logger.info(f"Registro {record_id} restaurado com sucesso.")

                if normalized_data: 
                    logger.info(f"Registro restaurado ID {record_id}. Reelegendo Golden Record para '{normalized_data}'.")
                    
                    all_records_for_gr_reelection = await self.repo.get_all_records_by_normalized_data(
                        dado_normalizado=normalized_data,
                        tipo_validacao=validation_type,
                        include_deleted=False 
                    )
                    
                    new_golden_record_candidate, _ = self._elect_golden_record_candidate(all_records_for_gr_reelection)
                    new_golden_record_id = new_golden_record_candidate.id if new_golden_record_candidate else None

                    await self._update_database_golden_record_statuses(
                        normalized_data, validation_type, new_golden_record_id, all_records_for_gr_reelection
                    )
                    logger.info(f"Processo de reeleição do Golden Record concluído para '{normalized_data}'. Novo GR ID: {new_golden_record_id}.")

                return {"status": "success", "message": f"Registro {record_id} restaurado com sucesso. Golden Record reavaliado.", "code": 200}
            else:
                logger.warning(f"Registro {record_id} não encontrado ou não estava deletado para restauração.")
                return {"status": "failed", "message": f"Registro {record_id} não encontrado ou não estava deletado logicamente.", "code": 404}
        except Exception as e:
            logger.error(f"Erro ao tentar restaurar record {record_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno ao restaurar registro: {e}", "code": 500}

def shutdown_service():
    """
    Função para desligar serviços, como fechar o pool de conexões do banco de dados.
    Esta função deve ser chamada de forma apropriada pelo framework que a utiliza (e.g., FastAPI's `on_shutdown`).
    """
    from app.database.manager import DatabaseManager 

    logger.info("Iniciando processo de desligamento do serviço...")
    if hasattr(DatabaseManager, '_instance') and DatabaseManager._instance._connection_pool:
        try:
            import asyncio
            if asyncio.get_event_loop().is_running():
                asyncio.ensure_future(DatabaseManager._instance.close_pool())
            else:
                asyncio.run(DatabaseManager._instance.close_pool())
            logger.info("Pool de conexões PostgreSQL fechado.")
        except Exception as e:
            logger.error(f"Erro ao fechar pool de conexões PostgreSQL: {e}", exc_info=True)
    else:
        logger.info("Nenhum pool de conexões ativo para fechar.")
