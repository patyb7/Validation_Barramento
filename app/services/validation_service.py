# app/services/validation_service.py
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import asyncio

# Importações de dependências para a CLASSE ValidationService
from app.auth.api_key_manager import APIKeyManager
from app.database.repositories import ValidationRecordRepository
from app.rules.decision_rules import DecisionRules
# Importe as CLASSES dos validadores aqui para que elas possam ser usadas no construtor
from app.rules.phone.validator import PhoneValidator
from app.rules.address.cep.validator import CEPValidator
from app.rules.email.validator import EmailValidator
from app.rules.document.cpf_cnpj.validator import CpfCnpjValidator
from app.rules.address.validator import AddressValidator

# Importação para o schema de registro de validação
from app.models.validation_record import ValidationRecord
from app.models.validation_request import ValidationRequest

# IMPORTANTE: Importe as mensagens de erro do módulo de dependências para evitar circularidade
from app.api.dependencies import INVALID_API_KEY_MESSAGE, API_KEY_INVALID_MESSAGE

logger = logging.getLogger(__name__)

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
        # Injeção de dependência dos validadores
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

        # Mapeamento de tipo de validação para o validador correspondente
        self.validators = {
            "phone": self.phone_validator,
            "address": self.address_validator,
            "email": self.email_validator,
            "document": self.cpf_cnpj_validator,
            "cep": self.cep_validator
        }

        logger.info("ValidationService inicializado com sucesso e validadores injetados.")

    async def validate_data(self, api_key_str: str, request: ValidationRequest) -> Dict[str, Any]:
        """
        Executa a validação do dado recebido na requisição.
        """
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
            # Chama o método `validate` do validador correspondente
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

            # Identificar o Golden Record antes de salvar o novo registro
            current_golden_record, all_related_records = await self._get_golden_record_for_data(
                normalized_data, request.tipo_validacao
            )

            # Determinar se a transação atual (se for válida) será o Golden Record
            is_this_transaction_golden_record_candidate = False
            if is_valid: # Apenas um registro válido pode ser candidato a GR
                is_this_transaction_golden_record_candidate = await self._should_this_be_golden_record(
                    current_golden_record, validation_result
                )

            # Salvar o registro no banco de dados
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
                is_golden_record=False, # Inicialmente False, será atualizado após salvar se for o caso
                usuario_criacao=app_name,
                usuario_atualizacao=app_name,
            )

            # Salva o registro primeiro para obter um ID, que é essencial para o GR
            saved_record_id = await self.repo.add_record(record_data)
            logger.info(f"Registro de validação salvo com ID: {saved_record_id}")

            golden_record_id_for_payload = None
            golden_record_data_for_payload = None
            is_this_transaction_golden_record_flag = False

            # Lógica para reeleição do Golden Record e atualização no banco
            if normalized_data: # Apenas se há dado normalizado para GR
                # Adicione o recorde recém-salvo à lista de registros relacionados para a eleição
                # É importante que o record_data tenha o ID atualizado
                record_data.id = saved_record_id

                # Para evitar complexidade de listas mutáveis, buscamos novamente ou ajustamos a lista
                # Idealmente, passamos `record_data` com o ID ou buscamos de novo.
                # Para simplicidade aqui, vamos assumir que `all_related_records` agora inclui o novo registro
                # e reelegemos o GR.
                # A forma mais robusta seria:
                all_records_for_gr_reelection = await self.repo.get_all_records_by_normalized_data(
                    dado_normalizado=normalized_data,
                    tipo_validacao=request.tipo_validacao,
                    include_deleted=False # Apenas registros ativos para eleição do GR
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
                        # ... outros campos ...
                    )

                # Atualizar o status de GR no banco de dados para todos os registros relacionados
                await self._update_database_golden_record_statuses(
                    normalized_data, request.tipo_validacao, golden_record_id_for_payload, all_records_for_gr_reelection
                )
                logger.info(f"Processo de eleição/reeleição do Golden Record concluído para '{normalized_data}'. GR ID: {golden_record_id_for_payload}.")


            return self._build_response_payload(
                record=record_data, # Use o record_data com o ID salvo
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

    # --- Métodos auxiliares para Golden Record (manter como antes) ---

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
            "golden_record_data": golden_record_data.model_dump(exclude_none=True) if golden_record_data else None
        }

    async def _get_golden_record_for_data(
        self, normalized_data: str, validation_type: str
    ) -> (Optional[ValidationRecord], List[ValidationRecord]):
        """
        Busca o Golden Record atual para um dado normalizado e tipo de validação.
        Retorna o Golden Record e todos os registros relacionados (ativos).
        """
        all_records = await self.repo.get_all_records_by_normalized_data(
            dado_normalizado=normalized_data,
            tipo_validacao=validation_type,
            include_deleted=False # Apenas registros ativos
        )

        if not all_records:
            return None, []

        # O Golden Record é o que tem 'is_golden_record = True'
        golden_record = next((rec for rec in all_records if rec.is_golden_record), None)

        # Se não houver um GR marcado, elegemos um entre os ativos
        if not golden_record:
            golden_record, _ = self._elect_golden_record_candidate(all_records)
            # Se um novo GR for eleito aqui, o status no banco será atualizado
            # na etapa subsequente (_update_database_golden_record_statuses)

        return golden_record, all_records

    def _elect_golden_record_candidate(self, records: List[ValidationRecord]) -> (Optional[ValidationRecord], str):
        """
        Elege um Golden Record entre uma lista de registros.
        Critérios:
        1. Válido = True
        2. Mais recente (maior ID) entre os válidos
        3. Más reciente (maior ID) entre os inválidos, se não houver válidos
        """
        if not records:
            return None, "No records to elect golden record from."

        # Separa registros válidos dos inválidos
        valid_records = [rec for rec in records if rec.is_valido]
        invalid_records = [rec for rec in records if not rec.is_valido]

        candidate = None
        reason = ""

        if valid_records:
            # Ordena registros válidos pelo ID em ordem decrescente (mais recente primeiro)
            valid_records.sort(key=lambda r: r.id, reverse=True)
            candidate = valid_records[0]
            reason = f"Eleito o registro válido mais recente (ID: {candidate.id})."
        elif invalid_records:
            # Se não houver válidos, ordena inválidos pelo ID em ordem decrescente
            invalid_records.sort(key=lambda r: r.id, reverse=True)
            candidate = invalid_records[0]
            reason = f"Eleito o registro inválido mais recente (ID: {candidate.id}), pois não há registros válidos."
        else:
            reason = "Nenhum candidato a Golden Record encontrado entre os registros fornecidos."

        return candidate, reason


    async def _should_this_be_golden_record(
        self, current_golden_record: Optional[ValidationRecord], new_validation_result # Recebe o ValidationResult do validador
    ) -> bool:
        """
        Determina se a validação atual deve se tornar o Golden Record.
        """
        # Se não há GR atual, o novo registro válido se torna o GR.
        if not current_golden_record:
            return True # O novo registro é o primeiro candidato a GR

        # Se o GR atual é inválido e o novo registro é válido, o novo se torna o GR.
        if not current_golden_record.is_valido and new_validation_result.is_valido:
            return True

        # Se ambos são válidos, o mais recente (maior ID) ou com melhor pontuação (se aplicável)
        # pode ser eleito. Por enquanto, a lógica de eleição já está em _elect_golden_record_candidate.
        # Aqui, estamos decidindo se o recém-validado deve SER o GR.
        # Se já existe um GR válido, um novo registro só o substituirá se for mais recente e também válido.
        # A lógica mais robusta para reeleição é feita após salvar o registro.
        return False # A eleição real acontece depois de salvar

    async def _update_database_golden_record_statuses(
        self,
        normalized_data: str,
        validation_type: str,
        new_golden_record_id: Optional[int],
        records_to_update: List[ValidationRecord] # Recebe a lista de registros afetados
    ):
        """
        Atualiza o status de Golden Record no banco de dados para os registros relacionados.
        """

        # Transforma a lista de objetos ValidationRecord em uma lista de IDs para otimizar a query
        record_ids = [rec.id for rec in records_to_update]

        if not record_ids:
            logger.info(f"Não há registros para atualizar o status de Golden Record para '{normalized_data}'.")
            return

        # 1. Desmarca todos os Golden Records antigos para este dado normalizado/tipo
        # Garante que apenas o novo GR eleito será marcado como True
        await self.repo.unset_golden_record_for_data(
            normalized_data=normalized_data,
            tipo_validacao=validation_type
        )
        logger.debug(f"Desmarcados GRs antigos para '{normalized_data}' ({validation_type}).")

        # 2. Marca o novo Golden Record, se houver um
        if new_golden_record_id:
            await self.repo.set_golden_record(new_golden_record_id)
            logger.debug(f"Definido novo Golden Record: ID {new_golden_record_id} para '{normalized_data}' ({validation_type}).")
        else:
            logger.info(f"Nenhum novo Golden Record eleito para '{normalized_data}' ({validation_type}).")

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
            # 1. Obter o registro antes de deletar para ter os dados normalizados
            record_to_delete = await self.repo.get_record_by_id(record_id)
            if not record_to_delete:
                logger.warning(f"Registro {record_id} não encontrado para soft delete.")
                return {"status": "failed", "message": f"Registro {record_id} não encontrado ou já deletado logicamente.", "code": 404}
            normalized_data = record_to_delete.dado_normalizado
            validation_type = record_to_delete.tipo_validacao
            was_golden_record = record_to_delete.is_golden_record
            # 2. Executar o soft delete
            success = await self.repo.soft_delete_record(record_id)
            if success:
                logger.info(f"Registro {record_id} soft-deletado com sucesso.")

                # 3. Reavaliar e reeleger Golden Record se o deletado era o GR ou se impactou o conjunto
                if normalized_data: # Apenas se houver dado normalizado para GR
                    if was_golden_record:
                        logger.info(f"Registro deletado ID {record_id} era o Golden Record. Reelegendo novo GR para '{normalized_data}'.")
                    else:
                        logger.info(f"Registro deletado ID {record_id} não era o Golden Record, mas ainda reavaliando para '{normalized_data}'.")

                    # Obter todos os registros REMANESCENTES (não deletados)
                    remaining_records = await self.repo.get_all_records_by_normalized_data(
                        dado_normalizado=normalized_data,
                        tipo_validacao=validation_type,
                        include_deleted=False # Apenas registros ativos
                    )

                    new_golden_record_candidate, _ = self._elect_golden_record_candidate(remaining_records)
                    new_golden_record_id = new_golden_record_candidate.id if new_golden_record_candidate else None

                    # Atualizar o status de GR no banco de dados para todos os registros relacionados
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

        try:
            # 1. Obter o registro antes de restaurar para ter os dados normalizados
            record_to_restore = await self.repo.get_record_by_id(record_id, include_deleted=True) # Busca mesmo se estiver deletado
            if not record_to_restore or not record_to_restore.is_deleted:
                logger.warning(f"Registro {record_id} não encontrado ou não estava deletado para restauração.")
                return {"status": "failed", "message": f"Registro {record_id} não encontrado ou não estava deletado logicamente.", "code": 404}

            normalized_data = record_to_restore.dado_normalizado
            validation_type = record_to_restore.tipo_validacao

            # 2. Executar a restauração
            success = await self.repo.restore_record(record_id)
            if success:
                logger.info(f"Registro {record_id} restaurado com sucesso.")

                # 3. Reavaliar e reeleger Golden Record
                if normalized_data: # Apenas se houver dado normalizado para GR
                    logger.info(f"Registro restaurado ID {record_id}. Reelegendo Golden Record para '{normalized_data}'.")

                    # Obter todos os registros (agora incluindo o restaurado)
                    all_records_for_gr_reelection = await self.repo.get_all_records_by_normalized_data(
                        dado_normalizado=normalized_data,
                        tipo_validacao=validation_type,
                        include_deleted=False # Apenas registros ativos para eleição do GR
                    )

                    new_golden_record_candidate, _ = self._elect_golden_record_candidate(all_records_for_gr_reelection)
                    new_golden_record_id = new_golden_record_candidate.id if new_golden_record_candidate else None

                    # Atualizar o status de GR no banco de dados para todos os registros relacionados
                    await self._update_database_golden_record_statuses(
                        normalized_data, validation_type, new_golden_record_id, all_records_for_gr_reelection
                    )
                    logger.info(f"Processo de reeleição do Golden Record concluído para '{normalized_data}'. Novo GR ID: {new_golden_record_id}.")

                return {"status": "success", "message": f"Registro {record_id} restaurado com sucesso. Golden Record reavaliado.", "code": 200}
            else:
                # Caso de falha na operação de restauração pelo repositório (ex: já não estava deletado)
                logger.warning(f"Registro {record_id} não encontrado ou não estava deletado para restauração.")
                return {"status": "failed", "message": f"Registro {record_id} não encontrado ou não estava deletado logicamente.", "code": 404}
        except Exception as e:
            logger.error(f"Erro ao tentar restaurar record {record_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno ao restaurar registro: {e}", "code": 500}

# A função shutdown_service não faz parte da classe ValidationService
# Ela é uma função independente que deve ser chamada no evento de shutdown do FastAPI.
def shutdown_service():
    """
    Função para desligar serviços, como fechar o pool de conexões do banco de dados.
    Esta função deve ser chamada de forma apropriada pelo framework que a utiliza (e.g., FastAPI's `on_shutdown`).
    """
    from app.database.manager import DatabaseManager # Importação local para evitar circular

    logger.info("Iniciando processo de desligamento do serviço...")
    if hasattr(DatabaseManager, '_instance') and DatabaseManager._instance._connection_pool:
        try:
            import asyncio
            if asyncio.get_event_loop().is_running():
                # Se o loop de eventos está rodando, agende o fechamento
                asyncio.ensure_future(DatabaseManager._instance.close_pool())
            else:
                # Se não está rodando, execute diretamente (para testes ou scripts simples)
                asyncio.run(DatabaseManager._instance.close_pool())
            logger.info("Pool de conexões PostgreSQL fechado.")
        except Exception as e:
            logger.error(f"Erro ao fechar pool de conexões PostgreSQL: {e}", exc_info=True)
    else:
        logger.info("Nenhum pool de conexões ativo para fechar.")