# app/services/validation_service.py

import logging
import asyncpg
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timezone
import uuid # Para manipulação de UUIDs
import json # Para json.dumps
from pydantic import BaseModel
from app.auth.api_key_manager import APIKeyManager
from app.database.repositories.validation_record_repository import ValidationRecordRepository
from app.database.repositories.log_repository import LogRepository, LogEntry
from app.database.repositories.qualification_repository import QualificationRepository
from app.rules.decision_rules import DecisionRules
from app.models.validation_record import ValidationRecord
from app.api.schemas.common import UniversalValidationRequest, ValidationResponse, HistoryRecordResponse
from app.rules.phone.validator import PhoneValidator
from app.rules.address.cep.validator import CEPValidator
from app.rules.email.validator import EmailValidator
from app.rules.document.cpf_cnpj.validator import CpfCnpjValidator
from app.rules.address.address_validator import AddressValidator
from app.rules.pessoa.nome.validator import NomeValidator
from app.rules.pessoa.genero.validator import SexoValidator
from app.rules.pessoa.rg.validator import RGValidator
from app.rules.pessoa.data_nascimento.validator import DataNascimentoValidator
from app.rules.pessoa.composite_validator import PessoaFullValidacao

# CONSTANTES DE MENSAGEM (para consistência)
API_KEY_INVALID_MESSAGE = "API Key inválida ou não autorizada."
INTERNAL_SERVER_ERROR_MESSAGE = "Ocorreu um erro interno inesperado."

logger = logging.getLogger(__name__)

class ValidationService:
    """
    Serviço central para orquestrar o processo de validação de dados.
    Responsável por rotear as requisições para o validador correto,
    aplicar regras de negócio, persistir resultados e gerenciar Golden Records.
    """
    def __init__(
        self,
        api_key_manager: APIKeyManager,
        repo: ValidationRecordRepository,
        qualification_repo: QualificationRepository, # NOVO: Injetar QualificationRepository
        decision_rules: DecisionRules,
        phone_validator: PhoneValidator,
        cep_validator: CEPValidator,
        email_validator: EmailValidator,
        cpf_cnpj_validator: CpfCnpjValidator,
        address_validator: AddressValidator,
        nome_validator: NomeValidator,
        sexo_validator: SexoValidator,
        rg_validator: RGValidator,
        data_nascimento_validator: DataNascimentoValidator,
        log_repo: LogRepository
    ):
        self.api_key_manager = api_key_manager
        self.repo = repo
        self.qualification_repo = qualification_repo # Armazenar o QualificationRepository
        # NOVO: A instância de DecisionRules agora é criada AQUI
        # e recebe ambos os repositórios (validation_repo e qualification_repo).
        self.decision_rules = DecisionRules(
            validation_repo=repo,
            qualification_repo=qualification_repo
        )
        self.log_repo = log_repo
        # Inicialize o PessoaFullValidacao aqui, passando as dependências
        self.pessoa_full_validacao_validator = PessoaFullValidacao( 
            phone_validator=phone_validator,
            cep_validator=cep_validator,
            email_validator=email_validator,
            cpf_cnpj_validator=cpf_cnpj_validator,
            address_validator=address_validator,
            nome_validator=nome_validator,
            sexo_validator=sexo_validator,
            rg_validator=rg_validator,
            data_nascimento_validator=data_nascimento_validator
        )
        # Dicionário de validadores, mapeando 'type' (da requisição) para a instância do validador
        self.validators = {
            "telefone": phone_validator,
            "cep": cep_validator,
            "email": email_validator,
            "cpf_cnpj": cpf_cnpj_validator,
            "endereco": address_validator,
            "nome": nome_validator,
            "genero": sexo_validator,
            "rg": rg_validator,
            "data_nascimento": data_nascimento_validator,
            "pessoa_completa": self.pessoa_full_validacao_validator 
        }
        logger.info("ValidationService inicializado com todos os validadores e repositórios.")

    async def validate_data(self, app_info: Dict[str, Any], request: UniversalValidationRequest) -> Dict[str, Any]:
        """
        Orquestra o processo de validação de um dado específico.
        """
        app_name_log = app_info.get('app_name', 'Desconhecido')
        operator_id_log = request.operator_id or app_name_log
        if not app_info or not app_info.get("is_active"):
            logger.warning(f"Tentativa de validação com API Key inválida ou inativa: {app_name_log}...")
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="AUTENTICACAO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"app_name": app_name_log, "status": "failed"},
                    status_operacao="FALHA",
                    mensagem_log="Tentativa de validação com API Key inválida ou inativa.",
                    client_entity_id_afetado=request.client_identifier 
                )
            )
            return {"status": "error", "message": API_KEY_INVALID_MESSAGE, "status_code": 401}

        logger.info(f"Requisição de validação recebida do app '{app_name_log}' para tipo '{request.validation_type}'.")

        validator = self.validators.get(request.validation_type)
        if not validator:
            logger.warning(f"Tipo de validação '{request.validation_type}' não suportado.")
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="VALIDACAO_DADO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"validation_type": request.validation_type, "data": request.data.model_dump() if hasattr(request.data, 'model_dump') else request.data}, 
                    status_operacao="FALHA",
                    mensagem_log=f"Tipo de validação '{request.validation_type}' não suportado.",
                    client_entity_id_afetado=request.client_identifier 
                )
            )
            return {"status": "error", "message": f"Tipo de validação '{request.validation_type}' não suportado.", "status_code": 400}

        try:
            # Passa todos os dados brutos e o client_identifier para o validador
            # Se for um validador composto (pessoa_completa), ele saberá como lidar com o dict.
            # Se for um validador simples (telefone), ele espera que request.data contenha o dado do telefone.
            validation_result = await validator.validate(request.data, client_identifier=request.client_identifier)

            # Converte dado_original para string se for um objeto ou dicionário
            original_data_str = json.dumps(request.data.model_dump()) if isinstance(request.data, BaseModel) else json.dumps(request.data) if isinstance(request.data, dict) else str(request.data)
            
            # Ajusta dado_normalizado para string se for um dicionário (para compatibilidade com VARCHAR)
            normalized_data_str = json.dumps(validation_result.get("dado_normalizado")) if isinstance(validation_result.get("dado_normalizado"), dict) else str(validation_result.get("dado_normalizado"))

            record = ValidationRecord(
                dado_original=original_data_str,
                dado_normalizado=normalized_data_str,
                is_valido=validation_result.get("is_valid"),
                mensagem=validation_result.get("mensagem"),
                origem_validacao=validation_result.get("origem_validacao", app_name_log),
                tipo_validacao=request.validation_type,
                app_name=app_name_log,
                client_identifier=request.client_identifier,
                validation_details=validation_result.get("details", {}),
                regra_negocio_codigo=validation_result.get("business_rule_applied", {}).get("code"),
                regra_negocio_descricao=validation_result.get("business_rule_applied", {}).get("description"),
                regra_negocio_tipo=validation_result.get("business_rule_applied", {}).get("type"),
                regra_negocio_parametros=validation_result.get("business_rule_applied", {}).get("parameters"),
                usuario_criacao=operator_id_log,
                usuario_atualizacao=operator_id_log,
                is_golden_record=False, # Definido inicialmente como False, DecisionRules irá atualizar
                golden_record_id=None, # Definido inicialmente como None, DecisionRules irá atualizar
                status_qualificacao="PENDING_DECISION", # NOVO: Status inicial para qualificação
                last_enrichment_attempt_at=None,
                client_entity_id=request.client_identifier # Ou extraído de request.data se houver um campo 'cclub'
            )
            
            persisted_record = await self.repo.create_record(record)
            if not persisted_record:
                raise Exception("Falha ao persistir o registro de validação inicial.")

            # Após a persistência, aplica as regras de decisão para qualificação
            # A instância de `decision_rules` já tem `validation_repo` e `qualification_repo`
            actions_summary = await self.decision_rules.apply_rules(persisted_record, app_info)

            # Recarrega o registro para ter os campos atualizados pelo decision_rules
            updated_persisted_record = await self.repo.get_record_by_id(persisted_record.id)
            if not updated_persisted_record:
                logger.error(f"Não foi possível recarregar o registro {persisted_record.id} após aplicação das regras de decisão.")
                # Continua com o record original, mas pode haver inconsistência nos logs/resposta
                updated_persisted_record = persisted_record 

            # A resposta deve ser um dicionário que FastAPI pode converter para ValidationResponse
            response_data = ValidationResponse(
                id=updated_persisted_record.id,
                dado_original=updated_persisted_record.dado_original,
                dado_normalizado=updated_persisted_record.dado_normalizado,
                is_valido=updated_persisted_record.is_valido,
                mensagem=updated_persisted_record.mensagem,
                origem_validacao=updated_persisted_record.origem_validacao,
                tipo_validacao=updated_persisted_record.tipo_validacao,
                app_name=updated_persisted_record.app_name,
                client_identifier=updated_persisted_record.client_identifier,
                short_id_alias=updated_persisted_record.short_id_alias,
                validation_details=updated_persisted_record.validation_details,
                data_validacao=updated_persisted_record.data_validacao,
                regra_negocio_codigo=updated_persisted_record.regra_negocio_codigo,
                regra_negocio_descricao=updated_persisted_record.regra_negocio_descricao,
                regra_negocio_tipo=updated_persisted_record.regra_negocio_tipo,
                regra_negocio_parametros=updated_persisted_record.regra_negocio_parametros,
                is_golden_record=updated_persisted_record.is_golden_record,
                golden_record_id=updated_persisted_record.golden_record_id,
                status_qualificacao=updated_persisted_record.status_qualificacao,
                last_enrichment_attempt_at=updated_persisted_record.last_enrichment_attempt_at,
                client_entity_id=updated_persisted_record.client_entity_id,
                status="success",
                message="Validação e qualificação concluídas com sucesso.", # Mensagem atualizada
                status_code=200
            ).model_dump(mode='json') # Converter para dicionário para retorno consistente

            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="VALIDACAO_DADO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={
                        "validation_type": request.validation_type,
                        "dado_normalizado": updated_persisted_record.dado_normalizado,
                        "is_valid": updated_persisted_record.is_valido,
                        "record_id": str(updated_persisted_record.id) if updated_persisted_record.id else None,
                        "actions_summary": actions_summary,
                        "final_status_qualificacao": updated_persisted_record.status_qualificacao # Novo: Logar o status final de qualificação
                    },
                    status_operacao="SUCESSO",
                    mensagem_log=f"Validação do tipo '{request.validation_type}' para '{updated_persisted_record.dado_normalizado}' concluída. Válido: {updated_persisted_record.is_valido}. Status Qualificação: {updated_persisted_record.status_qualificacao}. Record ID: {updated_persisted_record.id}",
                    client_entity_id_afetado=updated_persisted_record.client_entity_id 
                )
            )

            return response_data

        except Exception as e:
            logger.error(f"Erro no ValidationService.validate_data para tipo '{request.validation_type}': {e}", exc_info=True)
            # Tenta converter request.data para JSON para o log de erro, se possível
            error_data_for_log = request.data
            if hasattr(request.data, 'model_dump'):
                try:
                    error_data_for_log = request.data.model_dump()
                except Exception:
                    pass # Se falhar, mantém o objeto original
            elif isinstance(request.data, dict):
                pass
            else:
                error_data_for_log = str(request.data)


            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="ERRO_VALIDACAO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"validation_type": request.validation_type, "data": error_data_for_log, "error": str(e)},
                    status_operacao="FALHA",
                    mensagem_log=f"Erro durante a validação do tipo '{request.validation_type}': {e}",
                    client_entity_id_afetado=request.client_identifier 
                )
            )
            return {"status": "error", "message": INTERNAL_SERVER_ERROR_MESSAGE, "status_code": 500}

    async def get_validation_history(self, api_key_str: str, limit: int, include_deleted: bool) -> Dict[str, Any]:
        """
        Recupera o histórico de validações para uma determinada aplicação.
        """
        app_info = self.api_key_manager.get_app_info(api_key_str)
        app_name_log = app_info.get("app_name", "Desconhecido")
        operator_id_log = "N/A" # Para histórico, operador pode não ser conhecido

        if not app_info or not app_info.get("is_active"):
            logger.warning(f"Tentativa de acesso ao histórico com API Key inválida ou inativa: {api_key_str[:8]}...")
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="ACESSO_HISTORICO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"api_key_prefix": api_key_str[:8], "status": "failed"},
                    status_operacao="FALHA",
                    mensagem_log="Tentativa de acesso ao histórico com API Key inválida ou inativa.",
                    client_entity_id_afetado=None 
                )
            )
            return {"status": "error", "message": API_KEY_INVALID_MESSAGE, "status_code": 401}

        try:
            records = await self.repo.get_records_by_app_name(app_name_log, limit, include_deleted)
            history_list = [HistoryRecordResponse.model_validate(record).model_dump(mode='json') for record in records]
            
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="ACESSO_HISTORICO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"limit": limit, "include_deleted": include_deleted, "record_count": len(history_list)},
                    status_operacao="SUCESSO",
                    mensagem_log=f"Histórico de validações recuperado para o app '{app_name_log}'. {len(history_list)} registros.",
                    client_entity_id_afetado=None 
                )
            )
            return {
                "status": "success",
                "message": "Histórico de validações recuperado.",
                "history": history_list,
                "status_code": 200
            }
        except Exception as e:
            logger.error(f"Erro ao recuperar histórico para app '{app_name_log}': {e}", exc_info=True)
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="ERRO_HISTORICO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"limit": limit, "include_deleted": include_deleted, "error": str(e)},
                    status_operacao="FALHA",
                    mensagem_log=f"Erro ao recuperar histórico para o app '{app_name_log}': {e}",
                    client_entity_id_afetado=None 
                )
            )
            return {"status": "error", "message": INTERNAL_SERVER_ERROR_MESSAGE, "status_code": 500}

    async def soft_delete_record(self, api_key_str: str, record_id: uuid.UUID) -> Dict[str, Any]:
        """
        Executa o soft delete de um registro de validação.
        Requer permissão 'can_delete_records'.
        """
        app_info = self.api_key_manager.get_app_info(api_key_str)
        app_name_log = app_info.get('app_name', 'Desconhecido')
        operator_id_log = "N/A" # Pode ser um usuário autenticado em um cenário real

        record_to_delete = await self.repo.get_record_by_id(record_id)
        client_entity_id_affected = record_to_delete.client_entity_id if record_to_delete else None

        if not app_info or not app_info.get("is_active"):
            logger.warning(f"Tentativa de soft delete com API Key inválida ou inativa: {api_key_str[:8]}...")
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="SOFT_DELETE",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"record_id": str(record_id), "status": "failed", "reason": "API Key inválida"},
                    status_operacao="FALHA",
                    mensagem_log="Tentativa de soft delete com API Key inválida ou inativa.",
                    related_record_id=record_id,
                    client_entity_id_afetado=client_entity_id_affected 
                )
            )
            return {"status": "error", "message": API_KEY_INVALID_MESSAGE, "status_code": 401}
        
        if not app_info.get("can_delete_records"):
            logger.warning(f"Aplicação '{app_name_log}' sem permissão para soft delete de registro {record_id}.")
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="SOFT_DELETE",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"record_id": str(record_id), "status": "failed", "reason": "Sem permissão"},
                    status_operacao="FALHA",
                    mensagem_log=f"Aplicação '{app_name_log}' sem permissão para soft delete de registro {record_id}.",
                    related_record_id=record_id,
                    client_entity_id_afetado=client_entity_id_affected 
                )
            )
            return {"status": "error", "message": "Permissão negada: Sua API Key não tem privilégios para deletar registros.", "status_code": 403}

        try:
            success = await self.repo.soft_delete_record(record_id)
            if success:
                record = await self.repo.get_record_by_id(record_id)
                await self.log_repo.add_log_entry(
                    LogEntry(
                        tipo_evento="SOFT_DELETE",
                        app_origem=app_name_log,
                        usuario_operador=record.usuario_atualizacao if record else operator_id_log,
                        detalhes_evento_json={"record_id": str(record_id), "status": "success"},
                        status_operacao="SUCESSO",
                        mensagem_log=f"Registro {record_id} soft-deletado com sucesso.",
                        related_record_id=record_id,
                        client_entity_id_afetado=client_entity_id_affected 
                    )
                )
                return {"status": "success", "message": f"Registro {record_id} soft-deletado com sucesso.", "status_code": 200}
            else:
                await self.log_repo.add_log_entry(
                    LogEntry(
                        tipo_evento="SOFT_DELETE",
                        app_origem=app_name_log,
                        usuario_operador=operator_id_log,
                        detalhes_evento_json={"record_id": str(record_id), "status": "failed", "reason": "Não encontrado ou já deletado"},
                        status_operacao="FALHA",
                        mensagem_log=f"Falha ao soft-deletar registro {record_id}: Não encontrado ou já deletado.",
                        related_record_id=record_id,
                        client_entity_id_afetado=client_entity_id_affected 
                    )
                )
                return {"status": "error", "message": f"Registro {record_id} não encontrado ou já foi soft-deletado.", "status_code": 404}

        except Exception as e:
            logger.error(f"Erro ao soft-deletar registro {record_id} para app '{app_name_log}': {e}", exc_info=True)
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="ERRO_SOFT_DELETE",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"record_id": str(record_id), "error": str(e)},
                    status_operacao="FALHA",
                    mensagem_log=f"Erro ao soft-deletar registro {record_id}: {e}",
                    related_record_id=record_id,
                    client_entity_id_afetado=client_entity_id_affected 
                )
            )
            return {"status": "error", "message": INTERNAL_SERVER_ERROR_MESSAGE, "status_code": 500}

    async def restore_record(self, api_key_str: str, record_id: uuid.UUID) -> Dict[str, Any]:
        """
        Restaura um registro de validação que foi soft-deletado.
        Requer permissão 'can_delete_records'.
        """
        app_info = self.api_key_manager.get_app_info(api_key_str)
        app_name_log = app_info.get('app_name', 'Desconhecido')
        operator_id_log = "N/A" # Pode ser um usuário autenticado

        record_to_restore = await self.repo.get_record_by_id(record_id)
        client_entity_id_affected = record_to_restore.client_entity_id if record_to_restore else None

        if not app_info or not app_info.get("is_active"):
            logger.warning(f"Tentativa de restauração com API Key inválida ou inativa: {api_key_str[:8]}...")
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="RESTAURACAO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"record_id": str(record_id), "status": "failed", "reason": "API Key inválida"},
                    status_operacao="FALHA",
                    mensagem_log="Tentativa de restauração com API Key inválida ou inativa.",
                    related_record_id=record_id,
                    client_entity_id_afetado=client_entity_id_affected 
                )
            )
            return {"status": "error", "message": API_KEY_INVALID_MESSAGE, "status_code": 401}

        if not app_info.get("can_delete_records"):
            logger.warning(f"Aplicação '{app_name_log}' sem permissão para restaurar registro {record_id}.")
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="RESTAURACAO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"record_id": str(record_id), "status": "failed", "reason": "Sem permissão"},
                    status_operacao="FALHA",
                    mensagem_log=f"Aplicação '{app_name_log}' sem permissão para restaurar registro {record_id}.",
                    related_record_id=record_id,
                    client_entity_id_afetado=client_entity_id_affected 
                )
            )
            return {"status": "error", "message": "Permissão negada: Sua API Key não tem privilégios para restaurar registros.", "status_code": 403}

        try:
            success = await self.repo.restore_record(record_id)
            if success:
                record = await self.repo.get_record_by_id(record_id)
                await self.log_repo.add_log_entry(
                    LogEntry(
                        tipo_evento="RESTAURACAO",
                        app_origem=app_name_log,
                        usuario_operador=record.usuario_atualizacao if record else operator_id_log,
                        detalhes_evento_json={"record_id": str(record_id), "status": "success"},
                        status_operacao="SUCESSO",
                        mensagem_log=f"Registro {record_id} restaurado com sucesso.",
                        related_record_id=record_id,
                        client_entity_id_afetado=client_entity_id_affected 
                    )
                )
                return {"status": "success", "message": f"Registro {record_id} restaurado com sucesso.", "status_code": 200}
            else:
                await self.log_repo.add_log_entry(
                    LogEntry(
                        tipo_evento="RESTAURACAO",
                        app_origem=app_name_log,
                        usuario_operador=operator_id_log,
                        detalhes_evento_json={"record_id": str(record_id), "status": "failed", "reason": "Não encontrado ou não estava deletado"},
                        status_operacao="FALHA",
                        mensagem_log=f"Falha ao restaurar registro {record_id}: Não encontrado ou não estava soft-deletado.",
                        related_record_id=record_id,
                        client_entity_id_afetado=client_entity_id_affected 
                    )
                )
                return {"status": "error", "message": f"Registro {record_id} não encontrado ou não estava soft-deletado.", "status_code": 404}

        except Exception as e:
            logger.error(f"Erro ao restaurar registro {record_id} para app '{app_name_log}': {e}", exc_info=True)
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="ERRO_RESTAURACAO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"record_id": str(record_id), "error": str(e)},
                    status_operacao="FALHA",
                    mensagem_log=f"Erro ao restaurar registro {record_id}: {e}",
                    related_record_id=record_id,
                    client_entity_id_afetado=client_entity_id_affected 
                )
            )
            return {"status": "error", "message": INTERNAL_SERVER_ERROR_MESSAGE, "status_code": 500}
