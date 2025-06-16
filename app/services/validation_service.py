# app/services/validation_service.py
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone # Importa timezone para uso consistente
import json
# Importações internas do projeto
from ..auth.api_key_manager import APIKeyManager
from ..database.repositories import ValidationRecordRepository
from ..rules.decision_rules import DecisionRules
from app.models.validation_record import ValidationRecord # Importa o modelo ValidationRecord para tipagem
from app.models.validation_request import ValidationRequest

# Importar validadores específicos (Injeção de Dependência)
from ..rules.phone.validator import PhoneValidator
from ..rules.address.cep.validator import CEPValidator

logger = logging.getLogger(__name__)

class ValidationService:
    """
    Serviço centralizado para autenticação, validação de dados e gestão de registros.
    Orquestra a chamada aos validadores específicos, persistência e aplicação de regras de negócio.
    """

    def __init__(
        self,
        api_key_manager: APIKeyManager,
        repo: ValidationRecordRepository,
        decision_rules: DecisionRules,
        phone_validator: PhoneValidator,
        cep_validator: CEPValidator,
    ):
        self.api_key_manager = api_key_manager
        self.repo = repo
        self.decision_rules = decision_rules
        
        self.validators: Dict[str, Any] = {
            "telefone": phone_validator,
            "cep": cep_validator,
        }
        logger.info("ValidationService inicializado com sucesso.")

    async def _get_validator(self, validation_type: str) -> Any:
        validator = self.validators.get(validation_type)
        if not validator:
            logger.error(f"Tipo de validação '{validation_type}' não suportado ou validador não configurado.")
            raise ValueError(f"Tipo de validação '{validation_type}' não suportado ou validador não configurado.")
        return validator

    async def validate_data(self, api_key_str: str, request: ValidationRequest) -> Dict[str, Any]:
        logger.info(f"Recebida requisição para validar tipo '{request.validation_type}'. ID do Cliente: {request.client_identifier}. Operador: {request.operator_id}") 
        
        app_info = self.api_key_manager.get_app_info(api_key_str)

        if not app_info:
            logger.warning(f"Tentativa de acesso com API Key inválida: {api_key_str[:5]}...")
            return {"status": "error", "message": "API Key inválida.", "code": 401, "is_valid": False}

        app_name = app_info.get("app_name", "Desconhecido")
        logger.info(f"API Key '{app_name}' autenticada. Prosseguindo com validação de {request.validation_type}.")

        input_data_original = ""
        primary_validation_result: Dict[str, Any] = {}
        
        try:
            validator = await self._get_validator(request.validation_type)

            if request.validation_type == "telefone":
                phone_number = request.data.get("phone_number")
                country_hint = request.data.get("country_hint")
                if not phone_number:
                    raise ValueError("Para validação de 'telefone', o campo 'phone_number' é obrigatório em 'data'.")
                input_data_original = phone_number
                primary_validation_result = await validator.validate_phone(phone_number, country_hint)
            elif request.validation_type == "cep":
                cep_number = request.data.get("cep")
                if not cep_number:
                    raise ValueError("Para validação de 'cep', o campo 'cep' é obrigatório em 'data'.")
                input_data_original = cep_number
                primary_validation_result = await validator.validate_cep(cep_number)
            else:
                raise NotImplementedError(f"Validação para o tipo '{request.validation_type}' não implementada ou configurada neste serviço.")
            
            current_user_identifier = request.operator_id if request.operator_id else app_name

            # **CORREÇÃO CRÍTICA AQUI: Usando 'is_valido' diretamente no dicionário**
            record_base_data = {
                "dado_original": input_data_original,
                "dado_normalizado": primary_validation_result.get("dado_normalizado"),
                "is_valido": primary_validation_result.get("is_valid", False), # AGORA É 'is_valido' AQUI
                "mensagem": primary_validation_result.get("mensagem", "Validação concluída."),
                "origem_validacao": primary_validation_result.get("origem_validacao", "servico_generico"),
                "tipo_validacao": request.validation_type, 
                "app_name": app_name,
                "client_identifier": request.client_identifier,
                "validation_details": primary_validation_result.get("details", {}),
                "data_validacao": datetime.now(timezone.utc), # Usando UTC
                
                # Preenchendo campos de regras de negócio com base no resultado da validação primária
                "regra_negocio_codigo": primary_validation_result.get("business_rule_applied", {}).get("code"),
                "regra_negocio_descricao": primary_validation_result.get("business_rule_applied", {}).get("description"),
                "regra_negocio_tipo": primary_validation_result.get("business_rule_applied", {}).get("type"),
                "regra_negocio_parametros": primary_validation_result.get("business_rule_applied", {}).get("rule_definition"), 
                
                "usuario_criacao": current_user_identifier,
                "usuario_atualizacao": current_user_identifier,
                "is_deleted": False,
                "deleted_at": None,
                "created_at": datetime.now(timezone.utc), # Usando UTC
                "updated_at": datetime.now(timezone.utc) # Usando UTC
            }

            current_record_model = ValidationRecord(**record_base_data)

            # Ações pós-validação (regras de decisão)
            actions_summary = self.decision_rules.apply_post_validation_actions(current_record_model, app_info)
            current_record_model.validation_details["post_validation_actions_summary"] = actions_summary

            # Atualiza 'is_valido' no modelo com base no resultado final das regras de decisão, se aplicável
            if actions_summary.get('RN_TEL_INVALID_APP_status') == 'APPLIED_FAILURE':
                current_record_model.is_valido = False # Atualiza o campo 'is_valido' no modelo Pydantic
                current_record_model.mensagem = actions_summary.get('RN_TEL_INVALID_APP_message', current_record_model.mensagem)
                current_record_model.regra_negocio_codigo = actions_summary.get('RN_TEL_INVALID_APP_code', current_record_model.regra_negocio_codigo)
                current_record_model.regra_negocio_descricao = actions_summary.get('RN_TEL_INVALID_APP_message', current_record_model.regra_negocio_descricao)
                current_record_model.regra_negocio_tipo = actions_summary.get('RN_TEL_INVALID_APP_type', current_record_model.regra_negocio_tipo)
            
            # Buscando duplicatas
            # A CORREÇÃO ESTÁ AQUI NA PRÓXIMA LINHA!
            existing_record = await self.repo.find_duplicate_record(
                current_record_model.dado_original,
                current_record_model.tipo_validacao,
                app_name # <--- O ARGUMENTO 'app_name' FOI ADICIONADO AQUI.
            )

            record: ValidationRecord

            if existing_record:
                logger.info(f"Registro existente encontrado para '{current_record_model.dado_original}' ({current_record_model.tipo_validacao}). ID: {existing_record.id}. Atualizando...")
                
                current_record_model.usuario_atualizacao = current_user_identifier 
                current_record_model.updated_at = datetime.now(timezone.utc) 

                # Use model_dump sem by_alias=True aqui, pois os nomes dos campos já correspondem às colunas do DB
                update_data = current_record_model.model_dump(exclude={'id', 'created_at', 'usuario_criacao'}) 
                
                # Serialização de JSON
                if update_data.get('regra_negocio_parametros') is not None:
                    update_data['regra_negocio_parametros'] = json.dumps(update_data['regra_negocio_parametros'])
                else:
                    update_data['regra_negocio_parametros'] = None

                if update_data.get('validation_details') is not None:
                    update_data['validation_details'] = json.dumps(update_data['validation_details'])
                else:
                    update_data['validation_details'] = '{}'

                updated_record_obj = await self.repo.update_record(existing_record.id, update_data)
                
                record = updated_record_obj if updated_record_obj else existing_record
                if not updated_record_obj:
                    logger.warning(f"Falha ao atualizar registro {existing_record.id}. Retornando o registro original antes da tentativa de atualização.")
            else:
                logger.info(f"Nenhum registro existente encontrado para '{current_record_model.dado_original}' ({current_record_model.tipo_validacao}). Inserindo novo registro.")
                
                # Use model_dump sem by_alias=True aqui
                record_data_to_insert = current_record_model.model_dump() 
                
                # Serialização de JSON
                if record_data_to_insert.get('regra_negocio_parametros') is not None:
                    record_data_to_insert['regra_negocio_parametros'] = json.dumps(record_data_to_insert['regra_negocio_parametros'])
                else:
                    record_data_to_insert['regra_negocio_parametros'] = None

                if record_data_to_insert.get('validation_details') is not None:
                    record_data_to_insert['validation_details'] = json.dumps(record_data_to_insert['validation_details'])
                else:
                    record_data_to_insert['validation_details'] = '{}'

                inserted_record_obj = await self.repo.insert_record(record_data_to_insert)
                
                if not inserted_record_obj:
                    logger.error("Falha ao inserir novo registro de validação no banco de dados. Retornando erro interno.")
                    return {
                        "status": "error",
                        "message": "Falha ao persistir o registro de validação.",
                        "code": 500,
                        "is_valid": False,
                        "validation_details": {"error_type": "database_persistence_error"}
                    }
                record = inserted_record_obj
                logger.info(f"Novo registro de validação inserido para '{record.dado_original}'. ID: {record.id}")

            logger.info(f"Operação de registro concluída para ID {record.id}. Válido: {record.is_valido}, Regra de Negócio: {record.regra_negocio_codigo}.")

            response_payload = {
                "status": "success" if record.is_valido else "invalid", # Use 'is_valido' aqui
                "message": record.mensagem,
                "is_valid": record.is_valido, # Use 'is_valido' aqui
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
                "code": 200 if record.is_valido else 400 # Use 'is_valido' aqui
            }
            return response_payload

        except (ValueError, NotImplementedError) as e:
            logger.error(f"Erro de validação de entrada ou funcionalidade não implementada: {e}", exc_info=True)
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
                "message": f"Erro interno no servidor ao processar a validação: {e}",
                "code": 500,
                "is_valid": False,
                "validation_details": {"error_type": "internal_server_error"}
            }

    async def get_validation_history(self, api_key: str, limit: int = 10, include_deleted: bool = False) -> Dict[str, Any]:
        logger.info(f"Recebida requisição de histórico para API Key: {api_key[:5]}..., Limite: {limit}, Incluir Deletados: {include_deleted}")
        app_info = self.api_key_manager.get_app_info(api_key)

        if not app_info:
            logger.warning(f"Tentativa de acesso não autorizado ao histórico com API Key inválida: {api_key[:5]}...")
            return {"status": "error", "message": "API Key inválida.", "code": 401, "data": []}

        app_name = app_info.get("app_name", "Desconhecido")
        logger.info(f"API Key '{app_name}' autenticada para consulta de histórico.")

        try:
            records: List[ValidationRecord] = await self.repo.get_last_records(limit=limit, include_deleted=include_deleted)
            logger.info(f"Últimos {len(records)} registros de histórico recuperados (incluindo deletados: {include_deleted}).")

            history_data = [rec.model_dump(mode='json') for rec in records]

            return {"status": "success", "data": history_data, "message": "Histórico obtido com sucesso.", "code": 200}
        except Exception as e:
            logger.error(f"Erro interno ao buscar histórico de validação: {e}", exc_info=True)
            return {"status": "error", "message": "Erro interno ao buscar histórico.", "code": 500, "data": []}
            
    async def soft_delete_record(self, api_key: str, record_id: int) -> Dict[str, Any]:
        logger.info(f"Recebida requisição de soft delete para record_id: {record_id} pela API Key: {api_key[:5]}...")
        app_info = self.api_key_manager.get_app_info(api_key)

        if not app_info:
            logger.warning(f"Tentativa de soft delete com API Key inválida: {api_key[:5]}...")
            return {"status": "error", "message": "API Key inválida.", "code": 401}

        try:
            success = await self.repo.soft_delete_record(record_id) 
            if success:
                logger.info(f"Registro {record_id} soft-deletado com sucesso.")
                return {"status": "success", "message": f"Registro {record_id} deletado logicamente com sucesso.", "code": 200}
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
            return {"status": "error", "message": "API Key inválida.", "code": 401}
        
        try:
            success = await self.repo.restore_record(record_id)
            if success:
                logger.info(f"Registro {record_id} restaurado com sucesso.")
                return {"status": "success", "message": f"Registro {record_id} restaurado com sucesso.", "code": 200}
            else:
                logger.warning(f"Registro {record_id} não encontrado ou não estava deletado para restauração.")
                return {"status": "failed", "message": f"Registro {record_id} não encontrado ou não estava deletado logicamente.", "code": 404}
        except Exception as e:
            logger.error(f"Erro ao tentar restaurar record {record_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno ao restaurar registro: {e}", "code": 500}

def shutdown_service():
    from ..database.manager import DatabaseManager

    logger.info("Iniciando processo de desligamento do serviço...")
    if hasattr(DatabaseManager, '_instance') and DatabaseManager._instance._connection_pool:
        try:
            import asyncio
            asyncio.run(DatabaseManager._instance.close_pool()) 
            logger.info("Pool de conexões PostgreSQL fechado.")
        except Exception as e:
            logger.error(f"Erro ao fechar pool de conexões PostgreSQL: {e}", exc_info=True)
    else:
        logger.info("Nenhum pool de conexões ativo para fechar.")