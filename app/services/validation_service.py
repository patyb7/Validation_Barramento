# app/services/validation_service.py
import logging
import json
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timezone
import hashlib # Importa hashlib para gerar hash SHA256
import uuid # Importa uuid para golden_record_id (caso não tenha sido importado em modelos)

# Importações internas do projeto
from app.auth.api_key_manager import APIKeyManager
from app.database.repositories import ValidationRecordRepository
from app.rules.decision_rules import DecisionRules
from app.models.validation_record import ValidationRecord
# Importar UniversalValidationRequest do common.py, pois é o modelo de requisição da API
from app.api.schemas.common import UniversalValidationRequest 
# Assumindo que GoldenRecordSummary está em common.py ou em seu próprio arquivo de modelos
# Se estiver em common.py, ajuste o import para from app.api.schemas.common import GoldenRecordSummary
# Se não existir, defina-o abaixo ou em um novo arquivo de modelos se for complexo
try:
    from app.models.golden_record_summary import GoldenRecordSummary
except ImportError:
    # Fallback para GoldenRecordSummary se o modelo não for encontrado
    logger.warning("Não foi possível importar GoldenRecordSummary de app.models.golden_record_summary. Usando definição simplificada.")
    from pydantic import BaseModel # Adicionar BaseModel para o fallback
    class GoldenRecordSummary(BaseModel):
        id: uuid.UUID
        dado_original: str
        dado_normalizado: Optional[str] = None
        is_valido: bool
        app_name: str
        data_validacao: datetime
        class Config:
            from_attributes = True
            json_encoders = {
                datetime: lambda dt: dt.isoformat(),
                uuid.UUID: lambda u: str(u)
            }
            populate_by_name = True


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
        address_validator: AddressValidator 
    ):
        self.api_key_manager = api_key_manager
        self.repo = repo
        self.decision_rules = decision_rules

        # Atribuição dos validadores injetados
        self.phone_validator = phone_validator
        self.cep_validator = cep_validator
        self.email_validator = email_validator
        self.cpf_cnpj_validator = cpf_cnpj_validator
        self.address_validator = address_validator 

        self.validators: Dict[str, Any] = {
            "telefone": self.phone_validator, 
            "cep": self.cep_validator,      
            "email": self.email_validator,  
            "cpf_cnpj": self.cpf_cnpj_validator, 
            "endereco": self.address_validator, 
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

    async def _perform_data_validation(self, validation_type: str, data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Executa a validação específica do tipo de dado e retorna o resultado.
        """
        validator = await self._get_validator(validation_type)
        input_data_original_for_record = data 
        primary_validation_result: Dict[str, Any] = {}

        # Mapeia UniversalValidationRequest.data para o formato esperado pelos validadores
        if validation_type == "telefone":
            if not isinstance(data, str):
                raise ValueError("Para validação de 'telefone', o campo 'data' deve ser uma string.")
            phone_number = data
            primary_validation_result = await validator.validate(phone_number) 
        elif validation_type == "cep":
            if not isinstance(data, str):
                raise ValueError("Para validação de 'cep', o campo 'data' deve ser uma string.")
            cep_number = data
            primary_validation_result = await validator.validate(cep_number) 
        elif validation_type == "email":
            if not isinstance(data, str):
                raise ValueError("Para validação de 'email', o campo 'data' deve ser uma string.")
            email_address = data
            primary_validation_result = await validator.validate(email_address) 
        elif validation_type == "cpf_cnpj":
            if not isinstance(data, str):
                raise ValueError("Para validação de 'cpf_cnpj', o campo 'data' deve ser uma string.")
            document_number = data
            primary_validation_result = await validator.validate(document_number) 
        elif validation_type == "endereco":
            if not isinstance(data, dict):
                raise ValueError("Para validação de 'endereco', o campo 'data' deve ser um dicionário com os campos de endereço.")
            address_data = data 
            address_data_cleaned = {k: v for k, v in address_data.items() if v is not None}
            if not address_data_cleaned:
                raise ValueError("Para validação de 'endereco', ao menos um campo de endereço (logradouro, numero, etc.) é obrigatório em 'data'.")
            
            input_data_original_for_record = json.dumps(address_data_cleaned)
            primary_validation_result = await validator.validate(address_data_cleaned) 
        else:
            raise NotImplementedError(f"Validação para o tipo '{validation_type}' não implementada ou configurada neste serviço.")

        primary_validation_result["input_data_original"] = input_data_original_for_record
        return primary_validation_result

    def _create_initial_validation_record_model(self,
                                                    primary_validation_result: Dict[str, Any],
                                                    request: UniversalValidationRequest, 
                                                    app_name: str) -> ValidationRecord:
        """
        Cria e retorna uma instância inicial de ValidationRecord com os resultados da validação primária.
        Gera o 'client_entity_id' com base no client_identifier, dado normalizado e um identificador adicional (cclub ou cpssoa).
        """
        current_user_identifier = request.operator_identifier if request.operator_identifier else app_name 

        business_rule_params_from_validation = primary_validation_result.get("business_rule_applied", {}).get("parameters", {})

        determined_client_entity_id = ""
        if request.client_entity_id: 
            determined_client_entity_id = request.client_entity_id
        else: 
            identification_parts = [
                request.client_identifier,
                request.type, 
                primary_validation_result.get("dado_normalizado", ""),
                request.cclub, 
                request.cpssoa, 
                str(request.data) if isinstance(request.data, str) else None 
            ]
            composite_id_string = "-".join(filter(None, identification_parts)) 
            if composite_id_string: 
                determined_client_entity_id = hashlib.sha256(composite_id_string.encode('utf-8')).hexdigest()
            else:
                determined_client_entity_id = hashlib.sha256(str(uuid.uuid4()).encode('utf-8')).hexdigest()
        
        dado_original_for_record = primary_validation_result.get("input_data_original", "")
        if isinstance(dado_original_for_record, dict):
            dado_original_for_record = json.dumps(dado_original_for_record)

        record_model = ValidationRecord(
            dado_original=dado_original_for_record,
            dado_normalizado=primary_validation_result.get("dado_normalizado"),
            is_valido=primary_validation_result.get("is_valid", False),
            mensagem=primary_validation_result.get("mensagem", "Validação concluída."),
            origem_validacao=primary_validation_result.get("origem_validacao", "servico_generico"),
            tipo_validacao=request.type, 
            app_name=app_name,
            client_identifier=request.client_identifier,
            client_entity_id=determined_client_entity_id, 
            validation_details=primary_validation_result.get("details", {}),
            data_validacao=datetime.now(timezone.utc), 

            regra_negocio_codigo=primary_validation_result.get("business_rule_applied", {}).get("code"),
            regra_negocio_descricao=primary_validation_result.get("business_rule_applied", {}).get("message"), 
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
        # AQUI É ONDE apply_rules É CHAMADO
        actions_summary = await self.decision_rules.apply_rules( 
            record=record_model,
            app_info=app_info,
            repository=self.repo 
        )
        
        if record_model.validation_details is None:
            record_model.validation_details = {}
        
        record_model.validation_details["post_validation_actions_summary"] = actions_summary

        soft_delete_action = actions_summary.get('soft_delete_action', {})
        if soft_delete_action.get('status') == 'Applied' and soft_delete_action.get('code') == 'RN_A_001':
            record_model.is_deleted = True
            record_model.deleted_at = datetime.now(timezone.utc)
            logger.info(f"Registro ID {record_model.id} marcado para soft delete pela regra '{soft_delete_action.get('code')}'.")
        

    async def _handle_golden_record_logic(self,
                                            current_record_model: ValidationRecord,
                                            normalized_data: Optional[str],
                                            validation_type: str,
                                            app_info: Dict[str, Any]) -> Tuple[ValidationRecord, bool, Optional[uuid.UUID], Optional[GoldenRecordSummary]]: 
        """
        Gerencia a lógica de Golden Record: busca, persiste, elege e atualiza status.
        Retorna o registro persistido, se é o GR, o ID do GR e os dados do GR.
        """
        if not normalized_data or not current_record_model.is_valido: 
            current_record_model.is_golden_record = False
            current_record_model.golden_record_id = None
            logger.info(f"Registro ID {current_record_model.id} não elegível para Golden Record (não normalizado ou inválido).")
            return current_record_model, False, None, None

        golden_record_id: Optional[uuid.UUID] = None
        is_this_transaction_golden_record = False
        golden_record_data_summary: Optional[GoldenRecordSummary] = None

        if app_info.get('can_check_duplicates'): 
            existing_valid_records = await self.repo.get_all_records_by_normalized_data(
                dado_normalizado=normalized_data,
                tipo_validacao=validation_type,
                include_deleted=False 
            )
            logger.debug(f"Encontrados {len(existing_valid_records)} registros existentes válidos para '{normalized_data}'.")

            records_to_evaluate = [rec for rec in existing_valid_records if rec.id != current_record_model.id]
            records_to_evaluate.append(current_record_model)
            
            candidate_golden_record, best_score = self._elect_golden_record_candidate(records_to_evaluate)
            
            if candidate_golden_record:
                golden_record_id = candidate_golden_record.id
                is_this_transaction_golden_record = (candidate_golden_record.id == current_record_model.id)

                await self._update_database_golden_record_statuses(
                    normalized_data, validation_type, golden_record_id, records_to_evaluate
                )
                logger.info(f"Registro ID {candidate_golden_record.id} eleito como o novo Golden Record para '{normalized_data}' (score: {best_score}).")
                
                full_golden_record = await self.repo.get_record_by_id(golden_record_id)
                if full_golden_record:
                    golden_record_data_summary = GoldenRecordSummary(
                        id=full_golden_record.id,
                        dado_original=full_golden_record.dado_original,
                        dado_normalizado=full_golden_record.dado_normalizado,
                        is_valido=full_golden_record.is_valido,
                        app_name=full_golden_record.app_name,
                        data_validacao=full_golden_record.data_validacao
                    )
            else:
                logger.warning(f"Nenhum Golden Record eleito para '{normalized_data}'. Isso pode ocorrer se não houver registros válidos.")
                if current_record_model.is_valido:
                    golden_record_id = current_record_model.id
                    is_this_transaction_golden_record = True 
                    await self.repo.update_golden_record_status(
                        current_record_model.id, True, current_record_model.id
                    )
                    full_golden_record = await self.repo.get_record_by_id(golden_record_id)
                    if full_golden_record:
                        golden_record_data_summary = GoldenRecordSummary(
                            id=full_golden_record.id,
                            dado_original=full_golden_record.dado_original,
                            dado_normalizado=full_golden_record.dado_normalizado,
                            is_valido=full_golden_record.is_valido,
                            app_name=full_golden_record.app_name,
                            data_validacao=full_golden_record.data_validacao
                        )

        else:
            logger.info(f"Aplicação '{app_info.get('app_name')}' não tem permissão para verificar duplicatas. Pulando lógica de Golden Record.")
            
        return current_record_model, is_this_transaction_golden_record, golden_record_id, golden_record_data_summary

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
        
        if record.is_valido:
            score += 1000 

        if record.app_name == "CRM_Principal":
            score += 500
        elif record.app_name == "ERP_System":
            score += 450
        elif record.app_name == "Seguros App":
            score += 300
        elif record.app_name == "App_Marketing":
            score += 100
        else:
            score += 50 

        if record.validation_details:
            if record.tipo_validacao == "telefone":
                if record.validation_details.get("phonenumbers_valid"):
                    score += 50 
            elif record.tipo_validacao == "cep":
                if record.validation_details.get("address_found"):
                    score += 50 
            elif record.tipo_validacao == "email":
                if record.validation_details.get("is_syntax_valid"):
                    score += 40 
                if record.validation_details.get("domain_resolves"):
                    score += 60 
            elif record.tipo_validacao == "cpf_cnpj":
                if record.validation_details.get("is_valid_checksum"):
                    score += 70 
                if record.validation_details.get("status_receita_federal") == "REGULAR":
                    score += 100 
            elif record.tipo_validacao == "endereco":
                if record.validation_details.get("is_normalized"):
                    score += 40 
                if record.validation_details.get("is_geocoded"):
                    score += 80 

        if record.data_validacao:
            now = datetime.now(timezone.utc)
            time_diff_seconds = (now - record.data_validacao).total_seconds()
            
            max_recency_seconds = 365 * 24 * 3600 
            recency_bonus = max(0, int((max_recency_seconds - time_diff_seconds) / (86400 * 5))) 
            score += recency_bonus
        
        return score


    async def _update_database_golden_record_statuses(self, normalized_data: str, validation_type: str, golden_record_id: Optional[uuid.UUID], records_to_evaluate: List[ValidationRecord]): 
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


    async def validate_data(self, app_info: Dict[str, Any], request: UniversalValidationRequest) -> Dict[str, Any]: 
        """
        Processa uma requisição de validação de dados: autentica, valida, persiste,
        aplica regras de negócio e gerencia o Golden Record.
        """
        logger.info(f"Recebida requisição para validar tipo '{request.type}'. ID do Cliente: {request.client_identifier}. Operador: {request.operator_identifier}")

        app_name = app_info.get("app_name", "Desconhecido")
        logger.info(f"Requisição autenticada para a aplicação '{app_name}'. Proseguindo com validação de {request.type}.")

        input_data_original_for_logging = "" 
        final_persisted_record: Optional[ValidationRecord] = None 

        try:
            primary_validation_result = await self._perform_data_validation(request.type, request.data) 
            input_data_original_for_logging = primary_validation_result.get("input_data_original", "")

            current_record_model = self._create_initial_validation_record_model(
                primary_validation_result, request, app_name
            )
            
            if current_record_model.id: 
                current_record_model.short_id_alias = current_record_model.generate_short_id_alias()
                logger.debug(f"Generated short_id_alias for record {current_record_model.id}: {current_record_model.short_id_alias}")

            await self._apply_business_rules_to_record(current_record_model, app_info)

            persisted_record = await self.repo.create_record(current_record_model)
            if not persisted_record:
                logger.error("Falha ao criar novo registro durante a validação.")
                return {
                    "status": "error",
                    "message": "Erro interno no servidor ao processar a validação: Falha ao persistir o registro atual.",
                    "code": 500,
                    "is_valid": current_record_model.is_valido, 
                    "validation_details": current_record_model.validation_details,
                    "app_name": app_name,
                    "client_identifier": request.client_identifier,
                    "input_data_original": request.data,
                    "input_data_cleaned": current_record_model.dado_normalizado,
                    "tipo_validacao": request.type,
                    "origem_validacao": current_record_model.origem_validacao,
                    "regra_negocio_codigo": current_record_model.regra_negocio_codigo,
                    "regra_negocio_descricao": current_record_model.regra_negocio_descricao,
                    "regra_negocio_tipo": current_record_model.regra_negocio_tipo,
                    "regra_negocio_parametros": current_record_model.regra_negocio_parametros,
                    "usuario_criacao": request.operator_identifier,
                    "usuario_atualizacao": request.operator_identifier,
                    "client_entity_id": current_record_model.client_entity_id,
                    "short_id_alias": current_record_model.short_id_alias
                }

            logger.info(f"Novo registro criado para '{app_name}' ('{request.data}'). ID: {persisted_record.id}")

            final_persisted_record, is_this_transaction_golden_record, golden_record_id, golden_record_data = \
                await self._handle_golden_record_logic(
                    persisted_record, 
                    persisted_record.dado_normalizado, 
                    request.type, 
                    app_info 
                )

            logger.info(f"Operação de validação e Golden Record concluída para ID {final_persisted_record.id}. "
                                    f"Válido: {final_persisted_record.is_valido}. "
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
            logger.error(f"Erro inesperado durante o processamento da validação para '{input_data_original_for_logging}': {e}", exc_info=True)
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
        golden_record_id: Optional[uuid.UUID], 
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
            "short_id_alias": record.short_id_alias, 
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

    async def get_validation_history(self, app_info: Dict[str, Any], limit: int, include_deleted: bool) -> Dict[str, Any]: 
        """
        Obtém o histórico de registros de validação.
        Recebe app_info para verificação de permissões ou logging.
        """
        logger.info(f"Buscando histórico de validação para app '{app_info.get('app_name', 'Desconhecido')}': limite={limit}, incluir_deletados={include_deleted}")
        # A autenticação já deve ter ocorrido antes desta função ser chamada na rota
        
        try:
            records = await self.repo.get_last_records(limit=limit, include_deleted=include_deleted)
            for record in records:
                if record.id and not record.short_id_alias:
                    record.short_id_alias = record.generate_short_id_alias()
            
            return {
                "status": "success",
                "message": "Histórico obtido com sucesso.",
                "data": records
            }
        except Exception as e:
            logger.error(f"Erro ao obter histórico de validação: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Erro interno ao obter histórico: {e}",
                "code": 500,
                "data": []
            }


    async def soft_delete_record(self, app_info: Dict[str, Any], record_id: uuid.UUID) -> Dict[str, Any]: 
        """
        Executa o soft delete (exclusão lógica) de um registro de validação.
        Após o soft delete, reavalia e reelege o Golden Record para o dado normalizado, se necessário.
        """
        logger.info(f"Recebida requisição de soft delete para record_id: {record_id} pela aplicação: {app_info.get('app_name', 'Desconhecido')}...")

        if not app_info.get("can_delete_records"):
            logger.warning(f"Tentativa de soft delete não autorizado para record_id {record_id} por aplicação sem permissão: {app_info.get('app_name', 'Desconhecido')}.")
            return {"status": "error", "message": "Não autorizado ou sem permissão para deletar registros.", "code": 403}
        
        try:
            record_to_delete = await self.repo.get_record_by_id(record_id)
            if not record_to_delete:
                logger.warning(f"Tentativa de soft delete para record_id {record_id} falhou: Registro não encontrado.")
                return {"status": "error", "message": "Registro não encontrado.", "code": 404}

            if record_to_delete.is_deleted:
                logger.info(f"Registro {record_id} já está marcado como deletado. Nenhuma ação necessária.")
                return {"status": "success", "message": "Registro já estava marcado como deletado.", "code": 200}
            
            logger.info(f"Executando soft delete para o registro {record_id}.")
            deleted_successfully = await self.repo.soft_delete_record(record_id)

            if not deleted_successfully:
                logger.error(f"Falha ao executar soft delete para o registro {record_id}.")
                return {"status": "error", "message": "Falha ao deletar o registro.", "code": 500}
            
            logger.info(f"Registro {record_id} soft deletado com sucesso.")

            if record_to_delete.dado_normalizado:
                logger.info(f"Reavaliando Golden Record para dado normalizado '{record_to_delete.dado_normalizado}' após soft delete de {record_id}.")
                all_related_records = await self.repo.get_all_records_by_normalized_data(
                    dado_normalizado=record_to_delete.dado_normalizado,
                    tipo_validacao=record_to_delete.tipo_validacao,
                    include_deleted=False 
                )
                
                if record_to_delete.is_golden_record:
                    candidate_golden_record, best_score = self._elect_golden_record_candidate(all_related_records)
                    new_golden_record_id: Optional[uuid.UUID] = None
                    if candidate_golden_record:
                        new_golden_record_id = candidate_golden_record.id
                        logger.info(f"Novo Golden Record eleito para '{record_to_delete.dado_normalizado}': {new_golden_record_id}.")
                    else:
                        logger.warning(f"Nenhum novo Golden Record eleito para '{record_to_delete.dado_normalizado}' após soft delete. Todos os registros válidos foram deletados ou não existiam.")
                    
                    await self._update_database_golden_record_statuses(
                        record_to_delete.dado_normalizado, 
                        record_to_delete.tipo_validacao, 
                        new_golden_record_id, 
                        all_related_records 
                    )
                else:
                    logger.info(f"Registro {record_id} não era o Golden Record. Reavaliação de GR concluída sem alteração de GR principal.")
            else:
                logger.info(f"Registro {record_id} não possui dado normalizado, pulando reavaliação de Golden Record.")
            
            return {"status": "success", "message": f"Registro {record_id} deletado logicamente com sucesso.", "code": 200}
        except Exception as e:
            logger.error(f"Erro inesperado durante soft delete para record_id {record_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno ao deletar registro: {e}", "code": 500}


    async def restore_record(self, app_info: Dict[str, Any], record_id: uuid.UUID) -> Dict[str, Any]:
        """
        Restaura um registro de validação que foi logicamente deletado.
        Após a restauração, reavalia e reelege o Golden Record para o dado normalizado, se necessário.
        """
        logger.info(f"Recebida requisição de restauração para record_id: {record_id} pela aplicação: {app_info.get('app_name', 'Desconhecido')}...")

        if not app_info.get("can_delete_records"): # Reutilizando a permissão de delete para restaurar
            logger.warning(f"Tentativa de restauração não autorizada para record_id {record_id} por aplicação sem permissão: {app_info.get('app_name', 'Desconhecido')}.")
            return {"status": "error", "message": "Não autorizado ou sem permissão para restaurar registros.", "code": 403}

        try:
            record_to_restore = await self.repo.get_record_by_id(record_id, include_deleted=True)
            if not record_to_restore:
                logger.warning(f"Tentativa de restauração para record_id {record_id} falhou: Registro não encontrado.")
                return {"status": "error", "message": "Registro não encontrado.", "code": 404}

            if not record_to_restore.is_deleted:
                logger.info(f"Registro {record_id} já está ativo. Nenhuma ação necessária.")
                return {"status": "success", "message": "Registro já estava ativo.", "code": 200}

            logger.info(f"Executando restauração para o registro {record_id}.")
            restored_successfully = await self.repo.restore_record(record_id)

            if not restored_successfully:
                logger.error(f"Falha ao executar restauração para o registro {record_id}.")
                return {"status": "error", "message": "Falha ao restaurar o registro.", "code": 500}

            logger.info(f"Registro {record_id} restaurado com sucesso.")

            # Reavaliação do Golden Record após restauração
            if record_to_restore.dado_normalizado:
                logger.info(f"Reavaliando Golden Record para dado normalizado '{record_to_restore.dado_normalizado}' após restauração de {record_id}.")
                all_related_records = await self.repo.get_all_records_by_normalized_data(
                    dado_normalizado=record_to_restore.dado_normalizado,
                    tipo_validacao=record_to_restore.tipo_validacao,
                    include_deleted=False # Apenas registros ativos para eleição de GR
                )
                candidate_golden_record, best_score = self._elect_golden_record_candidate(all_related_records)
                new_golden_record_id: Optional[uuid.UUID] = None
                if candidate_golden_record:
                    new_golden_record_id = candidate_golden_record.id
                    logger.info(f"Novo Golden Record eleito para '{record_to_restore.dado_normalizado}': {new_golden_record_id}.")
                else:
                    logger.warning(f"Nenhum novo Golden Record eleito para '{record_to_restore.dado_normalizado}' após restauração.")
                
                await self._update_database_golden_record_statuses(
                    record_to_restore.dado_normalizado, 
                    record_to_restore.tipo_validacao, 
                    new_golden_record_id, 
                    all_related_records
                )
            else:
                logger.info(f"Registro {record_id} não possui dado normalizado, pulando reavaliação de Golden Record após restauração.")

            return {"status": "success", "message": f"Registro {record_id} restaurado com sucesso.", "code": 200}
        except Exception as e:
            logger.error(f"Erro inesperado durante a restauração para record_id {record_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno ao restaurar registro: {e}", "code": 500}

