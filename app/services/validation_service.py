# app/services/validation_service.py

import logging
import json
import uuid
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timezone, timedelta 
from pydantic import BaseModel
from fastapi import HTTPException, status 
from app.auth.api_key_manager import APIKeyManager
from app.database.repositories.validation_record_repository import ValidationRecordRepository
from app.database.repositories.log_repository import LogRepository, LogEntry
from app.database.repositories.qualification_repository import QualificationRepository
from app.rules.decision_rules import DecisionRules
from app.models.validation_record import ValidationRecord
from app.models.qualificacao_pendente import QualificacaoPendente
from app.models.qualificacao_pendente import InvalidosQualificados
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
PERMISSION_DENIED_MESSAGE = "Permissão negada para esta operação."
RECORD_NOT_FOUND_MESSAGE = "Registro não encontrado ou já foi processado."
INTERNAL_SERVER_ERROR_MESSAGE = "Ocorreu um erro interno inesperado. A equipe de desenvolvimento foi notificada."


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
        qualification_repo: QualificationRepository,
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
        pessoa_full_validacao_validator: PessoaFullValidacao,
        log_repo: LogRepository
    ):
        self.api_key_manager = api_key_manager
        self.repo = repo
        self.qualification_repo = qualification_repo
        self.decision_rules = decision_rules
        self.log_repo = log_repo
        
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
            "pessoa_completa": pessoa_full_validacao_validator
        }
        logger.info("ValidationService inicializado com todos os validadores e repositórios.")

    async def validate_data(self, app_info: Dict[str, Any], request: UniversalValidationRequest) -> Dict[str, Any]:
        """
        Orquestra o processo de validação de um dado específico.
        """
        app_name_log = app_info.get('app_name', 'Desconhecido')
        operator_id_log = request.operator_id or app_name_log # Usar operator_id da requisição ou nome do app

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
                    client_entity_id_afetado=request.client_identifier if isinstance(request.client_identifier, uuid.UUID) else None
                )
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=API_KEY_INVALID_MESSAGE)

        logger.info(f"Requisição de validação recebida do app '{app_name_log}' para tipo '{request.validation_type}'.")

        validator = self.validators.get(request.validation_type)
        if not validator:
            logger.warning(f"Tipo de validação '{request.validation_type}' não suportado.")
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="VALIDACAO_DADO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"validation_type": request.validation_type, "data": request.data.model_dump() if isinstance(request.data, BaseModel) else request.data},
                    status_operacao="FALHA",
                    mensagem_log=f"Tipo de validação '{request.validation_type}' não suportado.",
                    client_entity_id_afetado=request.client_identifier if isinstance(request.client_identifier, uuid.UUID) else None
                )
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Tipo de validação '{request.validation_type}' não suportado.")

        try:
            # Passa todos os dados brutos e o client_identifier para o validador
            validation_result = await validator.validate(request.data, client_identifier=request.client_identifier)

            # Converte dado_original para string se for um objeto Pydantic ou dicionário
            original_data_str = json.dumps(request.data.model_dump()) if isinstance(request.data, BaseModel) else json.dumps(request.data) if isinstance(request.data, dict) else str(request.data)
            
            # Ajusta dado_normalizado para string se for um dicionário (para compatibilidade com VARCHAR)
            normalized_data_str = json.dumps(validation_result.get("dado_normalizado")) if isinstance(validation_result.get("dado_normalizado"), dict) else str(validation_result.get("dado_normalizado"))

            # Cria o registro de validação inicial
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
                is_golden_record=False,
                golden_record_id=None,
                status_qualificacao="PENDING_DECISION", # Status inicial antes das regras de decisão
                last_enrichment_attempt_at=None,
                client_entity_id=None # Será preenchido pelo DecisionRules
            )
            
            # Persistir o registro inicial
            persisted_record = await self.repo.create_record(record)
            if not persisted_record:
                # Se a persistência inicial falhar, levantamos uma exceção
                logger.error("Falha ao persistir o registro de validação inicial.")
                raise Exception("Falha ao persistir o registro de validação inicial.")

            # Aplica as regras de decisão para qualificação e Golden Record
            # O `decision_rules` irá atualizar o `persisted_record` e lidar com `qualificacoes_pendentes`
            actions_summary = await self.decision_rules.apply_rules(persisted_record, app_info)

            # Recarrega o registro para ter todos os campos atualizados pelo decision_rules (principalmente status_qualificacao, is_golden_record e client_entity_id)
            updated_persisted_record = await self.repo.get_record_by_id(persisted_record.id)
            if not updated_persisted_record:
                logger.critical(f"Não foi possível recarregar o registro {persisted_record.id} após aplicação das regras de decisão. Possível inconsistência de dados.")
                # Fallback para o registro original se não conseguir recarregar, mas um alerta crítico é válido
                updated_persisted_record = persisted_record

            # Lógica para logar o resultado da validação com o status final de qualificação
            log_status = "SUCESSO" if updated_persisted_record.is_valido else "FALHA" # Log de sucesso/falha da validação
            log_message = f"Validação do tipo '{request.validation_type}' para '{updated_persisted_record.dado_normalizado}' concluída. Válido: {updated_persisted_record.is_valido}. Status Qualificação: {updated_persisted_record.status_qualificacao}. Record ID: {updated_persisted_record.id}"

            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="VALIDACAO_DADO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={
                        "validation_type": request.validation_type,
                        "dado_normalizado": updated_persisted_record.dado_normalizado,
                        "is_valid": updated_persisted_record.is_valido,
                        "record_id": str(updated_persisted_record.id),
                        "actions_summary": actions_summary,
                        "final_status_qualificacao": updated_persisted_record.status_qualificacao
                    },
                    status_operacao=log_status,
                    mensagem_log=log_message,
                    # Usa o client_entity_id real do Golden Record após a aplicação das regras de decisão
                    client_entity_id_afetado=updated_persisted_record.client_entity_id
                )
            )

            # A resposta agora é diretamente o objeto ValidationResponse model_dumped
            return ValidationResponse.model_validate(updated_persisted_record).model_dump(mode='json')

        except HTTPException as he:
            # Captura e relança HTTPExceptions geradas intencionalmente
            logger.warning(f"HTTPException durante a validação para tipo '{request.validation_type}': {he.status_code} - {he.detail}")
            # Log de erro específico para HTTPException
            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="ERRO_VALIDACAO_HTTP",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"validation_type": request.validation_type, "data": request.data.model_dump() if isinstance(request.data, BaseModel) else request.data, "status_code": he.status_code, "detail": he.detail},
                    status_operacao="FALHA",
                    mensagem_log=f"Erro HTTP durante a validação do tipo '{request.validation_type}': {he.detail}",
                    client_entity_id_afetado=request.client_identifier if isinstance(request.client_identifier, uuid.UUID) else None
                )
            )
            raise he # Relança a exceção HTTP para ser capturada pelo manipulador global

        except Exception as e:
            logger.error(f"Erro inesperado no ValidationService.validate_data para tipo '{request.validation_type}': {e}", exc_info=True)
            error_data_for_log = request.data
            if isinstance(request.data, BaseModel):
                try:
                    error_data_for_log = request.data.model_dump()
                except Exception:
                    pass
            elif isinstance(request.data, dict):
                pass
            else:
                error_data_for_log = str(error_data_for_log)

            await self.log_repo.add_log_entry(
                LogEntry(
                    tipo_evento="ERRO_INTERNO_VALIDACAO",
                    app_origem=app_name_log,
                    usuario_operador=operator_id_log,
                    detalhes_evento_json={"validation_type": request.validation_type, "data": error_data_for_log, "error": str(e)},
                    status_operacao="FALHA",
                    mensagem_log=f"Erro interno fatal durante a validação do tipo '{request.validation_type}': {e}",
                    client_entity_id_afetado=request.client_identifier if isinstance(request.client_identifier, uuid.UUID) else None
                )
            )
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=INTERNAL_SERVER_ERROR_MESSAGE)

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
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=API_KEY_INVALID_MESSAGE)

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
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=INTERNAL_SERVER_ERROR_MESSAGE)

    async def soft_delete_record(self, api_key_str: str, record_id: uuid.UUID) -> Dict[str, Any]:
        """
        Executa o soft delete de um registro de validação.
        Requer permissão 'can_delete_records'.
        """
        app_info = self.api_key_manager.get_app_info(api_key_str)
        app_name_log = app_info.get('app_name', 'Desconhecido')
        operator_id_log = "N/A" # Pode ser um usuário autenticado em um cenário real

        # Tenta obter o recorde antes de qualquer validação para pegar o client_entity_id_afetado
        record_to_delete = await self.repo.get_record_by_id(record_id)
        # client_entity_id_affected agora é o UUID do Golden Record, se o registro tiver um
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
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=API_KEY_INVALID_MESSAGE)
        
        # O middleware já verifica can_delete_records, mas é bom ter uma checagem aqui para garantir o log.
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
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PERMISSION_DENIED_MESSAGE + " Sua API Key não tem privilégios para deletar registros.")

        try:
            success = await self.repo.soft_delete_record(record_id)
            if success:
                # Recarrega o registro para obter dados atualizados de log, como usuario_atualizacao
                record = await self.repo.get_record_by_id(record_id)
                await self.log_repo.add_log_entry(
                    LogEntry(
                        tipo_evento="SOFT_DELETE",
                        app_origem=app_name_log,
                        usuario_operador=record.usuario_atualizacao if record else operator_id_log, # Usa o usuário que fez a última atualização se disponível
                        detalhes_evento_json={"record_id": str(record_id), "status": "success"},
                        status_operacao="SUCESSO",
                        mensagem_log=f"Registro {record_id} soft-deletado com sucesso.",
                        related_record_id=record_id,
                        client_entity_id_afetado=client_entity_id_affected
                    )
                )
                return {"message": f"Registro {record_id} soft-deletado com sucesso."}
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
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=RECORD_NOT_FOUND_MESSAGE)

        except HTTPException as he:
            raise he # Relança as HTTPExceptions intencionais
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
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=INTERNAL_SERVER_ERROR_MESSAGE)

    async def restore_record(self, api_key_str: str, record_id: uuid.UUID) -> Dict[str, Any]:
        """
        Restaura um registro de validação que foi soft-deletado.
        Requer permissão 'can_delete_records'.
        """
        app_info = self.api_key_manager.get_app_info(api_key_str)
        app_name_log = app_info.get('app_name', 'Desconhecido')
        operator_id_log = "N/A" # Pode ser um usuário autenticado

        # Tenta obter o recorde antes de qualquer validação para pegar o client_entity_id_afetado
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
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=API_KEY_INVALID_MESSAGE)

        # O middleware já verifica can_delete_records, mas é bom ter uma checagem aqui para garantir o log.
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
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PERMISSION_DENIED_MESSAGE + " Sua API Key não tem privilégios para restaurar registros.")

        try:
            success = await self.repo.restore_record(record_id)
            if success:
                # Recarrega o registro para obter dados atualizados de log
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
                return {"message": f"Registro {record_id} restaurado com sucesso."}
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
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=RECORD_NOT_FOUND_MESSAGE)

        except HTTPException as he:
            raise he # Relança as HTTPExceptions intencionais
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
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=INTERNAL_SERVER_ERROR_MESSAGE)