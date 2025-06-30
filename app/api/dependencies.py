# app/api/dependencies.py
import logging
import asyncio
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from fastapi import Header, HTTPException, status, Depends
from app.config.settings import settings
from app.database.manager import DatabaseManager
from app.auth.api_key_manager import APIKeyManager
from app.database.repositories import ValidationRecordRepository
from app.rules.decision_rules import DecisionRules
from app.rules.phone.validator import PhoneValidator
from app.rules.address.cep.validator import CEPValidator
from app.rules.email.validator import EmailValidator
from app.rules.document.cpf_cnpj.validator import CpfCnpjValidator
from app.rules.address.validator import AddressValidator
from app.models.validation_record import ValidationRecord
from app.models.validation_request import ValidationRequest

# --- Definição das mensagens de erro ---
INVALID_API_KEY_MESSAGE = "API Key inválida ou não fornecida."
API_KEY_INVALID_MESSAGE = "API Key inválida."
VALIDATION_SERVICE_NOT_READY_MESSAGE = "Serviço de validação não está pronto. Tente novamente mais tarde."

logger = logging.getLogger(__name__)

# A instância do DatabaseManager deve ser um singleton.
# É melhor obtê-la e gerenciar seu ciclo de vida no startup do FastAPI (api_main.py).
# Aqui, apenas a acessamos via get_db_manager() quando necessário.
# NÃO instancie DatabaseManager() diretamente aqui, pois ele pode não estar conectado.
# global_db_manager: Optional[DatabaseManager] = None # Não precisamos de uma global aqui, o singleton basta.

# APIKeyManager pode ser inicializado globalmente, pois não depende de outras instâncias complexas
# que requerem conexão assíncrona ou ordem de inicialização específica de outras classes de serviço.
# Ele apenas precisa das chaves de configuração, que vêm de `settings`.
global_api_key_manager = APIKeyManager(api_keys=settings.API_KEYS)


# --- Classes Auxiliares (como GoldenRecordSummary) ---
class GoldenRecordSummary(BaseModel):
    id: int
    dado_original: str
    dado_normalizado: str
    is_valido: bool


class ValidationService:
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
        self.phone_validator = phone_validator
        self.cep_validator = cep_validator
        self.email_validator = email_validator
        self.cpf_cnpj_validator = cpf_cnpj_validator
        self.address_validator = address_validator

        self.validators = {
            "phone": self.phone_validator,
            "address": self.address_validator,
            "email": self.email_validator,
            "document": self.cpf_cnpj_validator,
            "cep": self.cep_validator
        }

        logger.info("ValidationService inicializado com sucesso e validadores injetados.")

    async def validate_data(self, api_key_str: str, request: ValidationRequest) -> Dict[str, Any]:
        logger.info(f"Requisição de validação recebida para tipo '{request.tipo_validacao}' e API Key: {api_key_str[:5]}...")

        app_info = self.api_key_manager.get_app_info(api_key_str)
        if not app_info:
            logger.warning(f"Tentativa de validação com API Key inválida: {api_key_str[:5]}...")
            return {"status": "error", "message": INVALID_API_KEY_MESSAGE, "code": 401, "is_valid": False}

        app_name = app_info.get("app_name", "Desconhecido")
        logger.info(f"API Key '{app_name}' autenticada para validação de '{request.tipo_validacao}'.")

        validador = self.validators.get(request.tipo_validacao)
        if not validador:
            logger.warning(f"Tipo de validação '{request.tipo_validacao}' não suportado ou validador não configurado para app '{app_name}'.")
            return {
                "status": "invalid",
                "message": f"Tipo de validação '{request.tipo_validacao}' não suportado.",
                "is_valid": False,
                "code": 400,
                "validation_details": {"error": "UNSUPPORTED_VALIDATION_TYPE"},
                "app_name": app_name,
                "client_identifier": request.client_identifier,
                "input_data_original": request.dado_original,
                "input_data_cleaned": None,
                "tipo_validacao": request.tipo_validacao,
                "origem_validacao": "Service",
                "regra_negocio_codigo": None,
                "regra_negocio_descricao": None,
                "regra_negocio_tipo": None,
                "regra_negocio_parametros": None,
                "usuario_criacao": app_name,
                "usuario_atualizacao": app_name,
            }

        try:
            validation_result = await validador.validate(
                request.dado_original,
                regra_negocio_codigo=request.regra_negocio_codigo,
                regra_negocio_parametros=request.regra_negocio_parametros
            )

            is_valid = validation_result.is_valido
            message = validation_result.mensagem
            normalized_data = validation_result.dado_normalizado
            validation_details = validation_result.detalhes_validacao

            logger.info(f"Validação para '{request.tipo_validacao}' de '{request.dado_original[:20]}...' (app: {app_name}) resultou em válido: {is_valid}")

            current_golden_record, all_related_records = await self._get_golden_record_for_data(
                normalized_data, request.tipo_validacao
            )

            is_this_transaction_golden_record_candidate = False
            if is_valid:
                is_this_transaction_golden_record_candidate = await self._should_this_be_golden_record(
                    current_golden_record, validation_result
                )

            record_data = ValidationRecord(
                app_name=app_name,
                client_identifier=request.client_identifier,
                dado_original=request.dado_original,
                dado_normalizado=normalized_data,
                is_valido=is_valid,
                mensagem=message,
                validation_details=validation_details,
                tipo_validacao=request.tipo_validacao,
                origem_validacao="API",
                regra_negocio_codigo=request.regra_negocio_codigo,
                regra_negocio_descricao=validation_result.regra_negocio_descricao,
                regra_negocio_tipo=validation_result.regra_negocio_tipo,
                regra_negocio_parametros=request.regra_negocio_parametros,
                is_golden_record=False,
                usuario_criacao=app_name,
                usuario_atualizacao=app_name,
            )

            saved_record_id = await self.repo.add_record(record_data)
            logger.info(f"Registro de validação salvo com ID: {saved_record_id}")

            golden_record_id_for_payload = None
            golden_record_data_for_payload = None
            is_this_transaction_golden_record_flag = False

            if normalized_data:
                record_data.id = saved_record_id

                all_records_for_gr_reelection = await self.repo.get_all_records_by_normalized_data(
                    dado_normalizado=normalized_data,
                    tipo_validacao=request.tipo_validacao,
                    include_deleted=False
                )

                new_golden_record_candidate, _ = self._elect_golden_record_candidate(all_records_for_gr_reelection)

                if new_golden_record_candidate:
                    golden_record_id_for_payload = new_golden_record_candidate.id
                    is_this_transaction_golden_record_flag = (new_golden_record_candidate.id == saved_record_id)
                    golden_record_data_for_payload = GoldenRecordSummary(
                        id=new_golden_record_candidate.id,
                        dado_original=new_golden_record_candidate.dado_original,
                        dado_normalizado=new_golden_record_candidate.dado_normalizado,
                        is_valido=new_golden_record_candidate.is_valido,
                    )

                await self._update_database_golden_record_statuses(
                    normalized_data, request.tipo_validacao, golden_record_id_for_payload, all_records_for_gr_reelection
                )
                logger.info(f"Processo de eleição/reeleição do Golden Record concluído para '{normalized_data}'. GR ID: {golden_record_id_for_payload}.")

            return self._build_response_payload(
                record=record_data,
                is_this_transaction_golden_record=is_this_transaction_golden_record_flag,
                golden_record_id=golden_record_id_for_payload,
                golden_record_data=golden_record_data_for_payload
            )

        except Exception as e:
            logger.error(f"Erro inesperado ao validar dado para app '{app_name}': {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Erro interno no serviço de validação: {e}",
                "is_valid": False,
                "code": 500,
                "validation_details": {"error": str(e)},
                "app_name": app_name,
                "client_identifier": request.client_identifier,
                "input_data_original": request.dado_original,
                "input_data_cleaned": None,
                "tipo_validacao": request.tipo_validacao,
                "origem_validacao": "Service",
                "regra_negocio_codigo": request.regra_negocio_codigo,
                "regra_negocio_descricao": None,
                "regra_negocio_tipo": None,
                "regra_negocio_parametros": None,
                "usuario_criacao": app_name,
                "usuario_atualizacao": app_name,
            }

    def _build_response_payload(
        self,
        record: ValidationRecord,
        is_this_transaction_golden_record: bool,
        golden_record_id: Optional[int],
        golden_record_data: Optional[GoldenRecordSummary]
    ) -> Dict[str, Any]:
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
            "golden_record_data": golden_record_data.model_dump(exclude_none=True) if golden_record_data else None
        }

    async def _get_golden_record_for_data(
        self, normalized_data: str, validation_type: str
    ) -> (Optional[ValidationRecord], List[ValidationRecord]):
        all_records = await self.repo.get_all_records_by_normalized_data(
            dado_normalizado=normalized_data,
            tipo_validacao=validation_type,
            include_deleted=False
        )

        if not all_records:
            return None, []

        golden_record = next((rec for rec in all_records if rec.is_golden_record), None)

        if not golden_record:
            golden_record, _ = self._elect_golden_record_candidate(all_records)

        return golden_record, all_records

    def _elect_golden_record_candidate(self, records: List[ValidationRecord]) -> (Optional[ValidationRecord], str):
        if not records:
            return None, "No records to elect golden record from."

        valid_records = [rec for rec in records if rec.is_valido]
        invalid_records = [rec for rec in records if not rec.is_valido]

        candidate = None
        reason = ""

        if valid_records:
            valid_records.sort(key=lambda r: r.id, reverse=True)
            candidate = valid_records[0]
            reason = f"Eleito o registro válido mais recente (ID: {candidate.id})."
        elif invalid_records:
            invalid_records.sort(key=lambda r: r.id, reverse=True)
            candidate = invalid_records[0]
            reason = f"Eleito o registro inválido mais recente (ID: {candidate.id}), pois não há registros válidos."
        else:
            reason = "Nenhum candidato a Golden Record encontrado entre os registros fornecidos."

        return candidate, reason


    async def _should_this_be_golden_record(
        self, current_golden_record: Optional[ValidationRecord], new_validation_result
    ) -> bool:
        if not current_golden_record:
            return True

        if not current_golden_record.is_valido and new_validation_result.is_valido:
            return True

        return False

    async def _update_database_golden_record_statuses(
        self,
        normalized_data: str,
        validation_type: str,
        new_golden_record_id: Optional[int],
        records_to_update: List[ValidationRecord]
    ):
        record_ids = [rec.id for rec in records_to_update]

        if not record_ids:
            logger.info(f"Não há registros para atualizar o status de Golden Record para '{normalized_data}'.")
            return

        await self.repo.unset_golden_record_for_data(
            normalized_data=normalized_data,
            tipo_validacao=validation_type
        )
        logger.debug(f"Desmarcados GRs antigos para '{normalized_data}' ({validation_type}).")

        if new_golden_record_id:
            await self.repo.set_golden_record(new_golden_record_id)
            logger.debug(f"Definido novo Golden Record: ID {new_golden_record_id} para '{normalized_data}' ({validation_type}).")
        else:
            logger.info(f"Nenhum novo Golden Record eleito para '{normalized_data}' ({validation_type}).")

    async def get_validation_history(self, api_key: str, limit: int = 10, include_deleted: bool = False) -> Dict[str, Any]:
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
        logger.info(f"Recebida requisição de restauração para record_id: {record_id} pela API Key: {api_key[:5]}...")
        app_info = self.api_key_manager.get_app_info(api_key)

        if not app_info:
            logger.warning(f"Tentativa de restauração com API Key inválida: {api_key[:5]}...")
            return {"status": "error", "message": API_KEY_INVALID_MESSAGE, "code": 401}

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
async def get_db_manager() -> DatabaseManager:
    """Retorna a instância do DatabaseManager para injeção de dependência."""
    # O pool de conexões é inicializado no startup_event em api_main.py
    # Aqui, apenas garantimos que a instância singleton está disponível e conectada.
    db_mgr = DatabaseManager.get_instance(db_url=settings.DATABASE_URL)
    if not db_mgr._connection_pool or db_mgr._connection_pool.closed: # Verificação mais robusta
        logger.warning("DatabaseManager pool não está conectado na dependência. Tentando conectar...")
        try:
            await db_mgr.connect() # Tenta reconectar se não estiver ativo
            logger.info("DatabaseManager pool conectado com sucesso via dependência.")
        except Exception as e:
            logger.critical(f"Falha CRÍTICA ao conectar DatabaseManager na dependência: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro de conexão com o banco de dados."
            )
    return db_mgr

def get_api_key_manager() -> APIKeyManager:
    """Retorna a instância do APIKeyManager para injeção de dependência."""
    # Como global_api_key_manager é instanciado uma vez no escopo global deste módulo,
    # ele está pronto para ser retornado diretamente.
    return global_api_key_manager

async def get_validation_record_repository(
    db_mgr: DatabaseManager = Depends(get_db_manager)
) -> ValidationRecordRepository:
    """Retorna a instância do ValidationRecordRepository para injeção de dependência."""
    return ValidationRecordRepository(db_manager=db_mgr)

async def get_decision_rules(
    repo: ValidationRecordRepository = Depends(get_validation_record_repository)
) -> DecisionRules:
    """Retorna a instância de DecisionRules para injeção de dependência."""
    return DecisionRules(repo)

async def get_phone_validator(
    db_mgr: DatabaseManager = Depends(get_db_manager)
) -> PhoneValidator:
    """Retorna a instância de PhoneValidator para injeção de dependência."""
    return PhoneValidator(db_manager=db_mgr)

async def get_cep_validator(
    db_mgr: DatabaseManager = Depends(get_db_manager)
) -> CEPValidator:
    """Retorna a instância de CEPValidator para injeção de dependência."""
    return CEPValidator(db_manager=db_mgr)

async def get_email_validator(
    db_mgr: DatabaseManager = Depends(get_db_manager)
) -> EmailValidator:
    """Retorna a instância de EmailValidator para injeção de dependência."""
    return EmailValidator(db_manager=db_mgr)

async def get_cpf_cnpj_validator(
    db_mgr: DatabaseManager = Depends(get_db_manager)
) -> CpfCnpjValidator:
    """Retorna a instância de CpfCnpjValidator para injeção de dependência."""
    return CpfCnpjValidator(db_manager=db_mgr)

async def get_address_validator(
    db_mgr: DatabaseManager = Depends(get_db_manager),
    cep_val: CEPValidator = Depends(get_cep_validator) # Assume que AddressValidator pode precisar de CEPValidator
) -> AddressValidator:
    """Retorna a instância de AddressValidator para injeção de dependência."""
    # Garanta que o construtor do AddressValidator aceita ambos db_manager e cep_validator
    return AddressValidator(db_manager=db_mgr, cep_validator=cep_val)

async def get_validation_service(
    api_key_mgr: APIKeyManager = Depends(get_api_key_manager),
    repo: ValidationRecordRepository = Depends(get_validation_record_repository),
    dec_rules: DecisionRules = Depends(get_decision_rules),
    phone_val: PhoneValidator = Depends(get_phone_validator),
    cep_val: CEPValidator = Depends(get_cep_validator),
    email_val: EmailValidator = Depends(get_email_validator),
    cpf_cnpj_val: CpfCnpjValidator = Depends(get_cpf_cnpj_validator),
    address_val: AddressValidator = Depends(get_address_validator)
) -> ValidationService:
    """
    Dependência que fornece uma instância do ValidationService com todas as suas dependências injetadas.
    """
    return ValidationService(
        api_key_manager=api_key_mgr,
        repo=repo,
        decision_rules=dec_rules,
        phone_validator=phone_val,
        cep_validator=cep_val,
        email_validator=email_val,
        cpf_cnpj_validator=cpf_cnpj_val,
        address_validator=address_val
    )

async def get_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """
    Dependência para validar a X-API-Key do cabeçalho da requisição.
    """
    api_key_mgr = get_api_key_manager()
    if not api_key_mgr.is_valid_api_key(x_api_key):
        logger.warning(f"Tentativa de acesso com API Key inválida: {x_api_key[:5]}...")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_API_KEY_MESSAGE)
    return x_api_key

def shutdown_service():
    """
    Função para lidar com o desligamento gracioso do serviço,
    incluindo o fechamento do pool de conexões do banco de dados.
    """
    # Importação local para evitar dependências circulares na inicialização do módulo
    from app.database.manager import DatabaseManager

    logger.info("Iniciando processo de desligamento do serviço...")
    # Verifica se a instância do DatabaseManager existe e se o pool de conexões foi inicializado
    if hasattr(DatabaseManager, '_instance') and DatabaseManager._instance._connection_pool:
        try:
            # Verifica se o loop de eventos asyncio está rodando para garantir o correto agendamento do fechamento
            # Esta função é para ser chamada em um contexto onde o loop de eventos pode já ter parado.
            # O ideal é que o 'on_shutdown' do FastAPI lide com isso, como em api_main.py
            db_manager_instance = DatabaseManager._instance
            if db_manager_instance._connection_pool and not db_manager_instance._connection_pool.closed:
                 # Tentativa de fechar o pool se ainda estiver aberto.
                 # Pode ser necessário um `asyncio.run` se o loop de eventos não estiver ativo.
                 # No entanto, a forma mais segura é delegar isso ao app.on_event("shutdown")
                 # como já está sendo feito em api_main.py
                 logger.info("Tentando fechar pool de conexões PostgreSQL no shutdown_service da dependência (pode ser redundante).")
                 # Uma chamada síncrona aqui é arriscada se o pool é assíncrono.
                 # Melhor deixar o app.on_event("shutdown") em api_main.py ser o responsável principal.
                 pass
        except Exception as e:
            logger.error(f"Erro ao tentar fechar pool de conexões PostgreSQL em shutdown_service da dependência: {e}", exc_info=True)
    else:
        logger.info("Nenhum pool de conexões ativo para fechar em shutdown_service da dependência.")