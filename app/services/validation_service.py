# app/services/validation_service.py

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.auth.api_key_manager import APIKeyManager
from app.database.repositories import ValidationRecordRepository
from app.models.validation_record import ValidationRecord
from app.rules.decision_rules import DecisionRules

# Importar validadores específicos
from app.rules.phone.validator import PhoneValidator # Corrigido para 'validator' conforme o arquivo real

# Configuração de logging.
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class ValidationService:
    """
    Serviço centralizado para autenticação, validação de dados e gestão de registros.
    Orquestra a chamada aos validadores específicos, persistência e aplicação de regras de negócio.
    """

    def __init__(self, 
                 api_key_manager: APIKeyManager, 
                 repo: ValidationRecordRepository, 
                 decision_rules: DecisionRules):
        """
        Inicializa o ValidationService.

        Args:
            api_key_manager: Gerenciador de chaves de API para autenticação.
            repo: Repositório para operações de banco de dados em ValidationRecord.
            decision_rules: Regras de negócio a serem aplicadas pós-validação.
        """
        self.api_key_manager = api_key_manager
        self.repo = repo
        self.decision_rules = decision_rules
        # Mapeamento de tipo de validação para a instância do validador correspondente.
        self.validators: Dict[str, Any] = {
            "phone": PhoneValidator(), # Instancie seus validadores aqui
            # "email": EmailValidator(), # Adicione outros validadores conforme necessário
            # "address": AddressValidator(),
            # "document": DocumentValidator(),
        }
        logger.info("ValidationService inicializado com sucesso.")

    def _get_validator(self, validation_type: str):
        """
        Retorna a instância do validador para o tipo de validação especificado.
        Levanta um ValueError se o tipo não for suportado.
        """
        validator = self.validators.get(validation_type)
        if not validator:
            raise ValueError(f"Tipo de validação '{validation_type}' não suportado ou validador não configurado.")
        return validator

    def validate_data(self, # Renomeado de validate_and_record_data para validate_data
                               api_key: str, 
                               validation_type: str, 
                               data: Dict[str, Any], # Alterado de data_to_validate: str para data: Dict[str, Any]
                               client_identifier: Optional[str] = None) -> Dict[str, Any]:
        """
        Valida um dado (telefone, e-mail, etc.), autentica a aplicação chamadora,
        registra o resultado e aplica regras de decisão de negócio.

        Args:
            api_key: Chave de API da aplicação chamadora.
            validation_type: O tipo de validação a ser realizada (ex: "phone", "email", "document").
            data: Um dicionário contendo os dados a serem validados.
                  Para "phone", espera-se {"phone_number": "...", "country_hint": "..."}.
            client_identifier: Identificador do cliente associado ao dado (CPF, CNPJ, etc.).

        Returns:
            Um dicionário contendo o status da validação, mensagem e detalhes.
        """
        logger.info(f"Recebida solicitação para validar do tipo '{validation_type}'. Client ID: {client_identifier}")
        app_info = self.api_key_manager.get_app_info(api_key)

        if not app_info:
            logger.warning(f"Tentativa de acesso com API Key inválida: {api_key[:5]}...") # Loga só o início da key
            return {"status": "error", "message": "API Key Inválida.", "code": 401}

        app_name = app_info.get("app_name", "Desconhecido")
        logger.info(f"API Key '{app_name}' autenticada. Prosseguindo com a validação de {validation_type}.")

        # Extrai os dados específicos para o validador
        input_data_original = data.get("phone_number", "") if validation_type == "phone" else str(data) # Adapta para outros tipos
        country_hint = data.get("country_hint") if validation_type == "phone" else None

        record_data = {
            "dado_original": input_data_original, # Mantenha o original completo ou uma representação
            "dado_normalizado": "", # Será preenchido pelo validador
            "valido": False,
            "mensagem": "Falha na validação.",
            "tipo_validacao": validation_type,
            "app_name": app_name,
            "client_identifier": client_identifier,
            "origem_validacao": "servico_generico",
            "regra_codigo": None,
            "validation_details": {},
            "data_validacao": datetime.now() # Adiciona a data de validação aqui
        }

        try:
            validator = self._get_validator(validation_type)
            # Adapta a chamada do validador para o tipo de dado esperado
            if validation_type == "phone":
                validation_result = validator.validate(input_data_original, country_hint)
            else:
                # Para outros tipos de validação, você precisaria adaptar a chamada
                # Ex: validation_result = validator.validate(input_data_original)
                raise NotImplementedError(f"Validação para '{validation_type}' ainda não implementada para o service.")
            
            record_data["valido"] = validation_result["is_valid"]
            record_data["dado_normalizado"] = validation_result.get("cleaned_data", "")
            record_data["mensagem"] = validation_result["message"]
            record_data["origem_validacao"] = validation_result.get("source", "servico_generico")
            record_data["validation_details"] = validation_result.get("details", {})
            record_data["regra_codigo"] = validation_result.get("rule_code")

        except NotImplementedError as nie:
            logger.error(f"Erro de implementação: {nie}")
            record_data["mensagem"] = str(nie)
            record_data["origem_validacao"] = "servico_interno"
            record_data["regra_codigo"] = "SVC001" # Código para erro de serviço
        except ValueError as ve:
            logger.error(f"Erro de configuração do validador para '{validation_type}': {ve}", exc_info=True)
            record_data["valido"] = False
            record_data["mensagem"] = f"Erro interno: Tipo de validação não suportado ou validador ausente. Detalhe: {ve}"
            record_data["origem_validacao"] = "servico_interno"
            record_data["regra_codigo"] = "SVC002" # Código para validador não encontrado
        except Exception as e:
            logger.error(f"Erro inesperado durante a validação para '{input_data_original}': {e}", exc_info=True)
            record_data["valido"] = False
            record_data["mensagem"] = f"Erro inesperado durante a validação: {e}"
            record_data["origem_validacao"] = "servico_interno"
            record_data["regra_codigo"] = "SVC003" # Código para erro inesperado

        # Criar o objeto ValidationRecord a partir dos dados coletados
        record = ValidationRecord(**record_data)
        
        # Persistir o registro no banco de dados
        try:
            record_id = self.repo.insert_record(record)
            record.id = record_id # Garante que o ID do registro seja atualizado após a inserção
            logger.info(f"Registro de validação para ID {record.id} salvo no DB. Válido: {record.valido}.")
        except Exception as e:
            logger.error(f"Falha ao persistir registro de validação para '{record.dado_original}': {e}", exc_info=True)
            return {
                "status": "error", 
                "message": f"Erro interno ao salvar o registro de validação: {e}", 
                "code": 500, 
                "validation_status": "failed_to_save"
            }

        # Aplicar regras de decisão de negócio pós-validação
        decision_actions_result = {}
        try:
            decision_actions_result = self.decision_rules.apply_post_validation_actions(record, app_info)
            logger.info(f"Regras de decisão aplicadas para registro ID {record.id}. Resultado: {decision_actions_result}")
        except Exception as e:
            logger.error(f"Erro ao aplicar regras de decisão pós-validação para registro ID {record.id}: {e}", exc_info=True)
            decision_actions_result["error_applying_rules"] = str(e)

        # Retornar o resultado da validação
        response = {
            "status": "success" if record.valido else "invalid",
            "message": record.mensagem,
            "is_valid": record.valido,
            "validation_details": record.validation_details,
            "app_info": {"app_name": record.app_name}, # Mapeia para o 'app_info' do response_model
            "record_id": record.id 
        }

        # Adiciona dado_original e dado_normalizado ao retorno se a validação não falhou internamente
        if record.dado_original: # Pode ser vazio se a entrada original for inválida
            response["input_data_original"] = record.dado_original
        if record.dado_normalizado: # Pode ser vazio se não foi normalizado
            response["input_data_cleaned"] = record.dado_normalizado


        if not record.valido:
            response["code"] = 400 # Bad Request para dados inválidos
            response["message"] = f"Dado inválido: {record.mensagem}"
        else:
             response["code"] = 200
        
        return response


    def get_validation_history(self, 
                               api_key: str, 
                               limit: int = 10, 
                               include_deleted: bool = False) -> Dict[str, Any]: # Adicionado include_deleted
        """
        Recupera o histórico de validações. Retorna os últimos registros globais ou filtrados.
        Requer autenticação de API Key.

        Args:
            api_key (str): Chave de API para autenticar a aplicação chamadora.
            limit (int): O número máximo de registros a serem retornados.
            include_deleted (bool): Se `True`, inclui registros marcados como deletados logicamente.

        Returns:
            Dict[str, Any]: Um dicionário contendo o status, os dados do histórico e uma mensagem.
        """
        logger.info(f"Recebida solicitação de histórico para API Key: {api_key[:5]}..., Limit: {limit}, Include Deleted: {include_deleted}")
        app_info = self.api_key_manager.get_app_info(api_key)

        if not app_info:
            logger.warning(f"Tentativa de acesso não autorizado ao histórico com API Key inválida: {api_key[:5]}...")
            return {"status": "error", "message": "API Key Inválida.", "code": 401}

        app_name = app_info.get("app_name", "Desconhecido")
        logger.info(f"API Key '{app_name}' autenticada para consulta de histórico.")

        try:
            # A chamada ao repositório deve agora incluir o parâmetro include_deleted
            records: List[ValidationRecord] = self.repo.get_last_records(limit=limit, include_deleted=include_deleted)
            logger.info(f"Últimos {len(records)} registros de histórico recuperados (incluindo deletados: {include_deleted}).")

            # Mapear os objetos ValidationRecord para dicionários para a resposta da API
            history_data = [
                {
                    "id": rec.id, # O nome do campo na resposta da API deve ser 'id' (conforme HistoryRecordResponse)
                    "input_data_original": rec.dado_original,
                    "input_data_cleaned": rec.dado_normalizado,
                    "valido": rec.valido,
                    "mensagem": rec.mensagem,
                    "origem_validacao": rec.origem_validacao,
                    "tipo_validacao": rec.tipo_validacao, # O campo correto do modelo
                    "data_validacao": rec.data_validacao.isoformat(), # Formato ISO para data
                    "app_name": rec.app_name,
                    "client_identifier": rec.client_identifier,
                    "regra_codigo": rec.regra_codigo,
                    "validation_details": rec.validation_details,
                    "is_deleted": rec.is_deleted,
                    "deleted_at": rec.deleted_at.isoformat() if rec.deleted_at else None
                }
                for rec in records
            ]

            return {"status": "success", "data": history_data, "message": "Histórico recuperado com sucesso.", "code": 200}
        except Exception as e:
            logger.error(f"Erro interno ao buscar histórico de validações: {e}", exc_info=True)
            return {"status": "error", "message": "Erro interno ao buscar histórico.", "code": 500}
            

    def soft_delete_record(self, api_key: str, record_id: int) -> Dict[str, Any]:
        """
        Marca um registro de validação como 'deletado' sem removê-lo fisicamente.
        Requer autenticação por API Key.
        """
        logger.info(f"Recebida solicitação de soft delete para record_id: {record_id} por API Key: {api_key[:5]}...")
        app_info = self.api_key_manager.get_app_info(api_key)

        if not app_info:
            logger.warning(f"Tentativa de soft delete com API Key inválida: {api_key[:5]}...")
            return {"status": "error", "message": "API Key Inválida.", "code": 401}

        try:
            success = self.repo.soft_delete_record(record_id)
            if success:
                logger.info(f"Registro {record_id} marcado como deletado logicamente.")
                return {"status": "success", "message": f"Registro {record_id} deletado logicamente com sucesso."}
            else:
                logger.warning(f"Registro {record_id} não encontrado ou já deletado.")
                return {"status": "failed", "message": f"Registro {record_id} não encontrado ou já deletado.", "code": 404}
        except Exception as e:
            logger.error(f"Erro ao tentar deletar logicamente o registro {record_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno ao deletar registro: {e}", "code": 500}

    def restore_record(self, api_key: str, record_id: int) -> Dict[str, Any]:
        """
        Restaura um registro de validação deletado logicamente, tornando-o ativo novamente.
        Requer autenticação por API Key.
        """
        logger.info(f"Recebida solicitação de restauração para record_id: {record_id} por API Key: {api_key[:5]}...")
        app_info = self.api_key_manager.get_app_info(api_key)

        if not app_info:
            logger.warning(f"Tentativa de restauração com API Key inválida: {api_key[:5]}...")
            return {"status": "error", "message": "API Key Inválida.", "code": 401}
        
        try:
            success = self.repo.restore_record(record_id)
            if success:
                logger.info(f"Registro {record_id} restaurado com sucesso.")
                return {"status": "success", "message": f"Registro {record_id} restaurado com sucesso."}
            else:
                logger.warning(f"Registro {record_id} não encontrado ou não estava deletado.")
                return {"status": "failed", "message": f"Registro {record_id} não encontrado ou não estava deletado.", "code": 404}
        except Exception as e:
            logger.error(f"Erro ao tentar restaurar o registro {record_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno ao restaurar registro: {e}", "code": 500}


# Função para garantir que o pool de conexões seja fechado ao encerrar o programa
def shutdown_service():
    """
    Função de shutdown para liberar recursos, como o pool de conexões do banco de dados.
    """
    from app.database.manager import DatabaseManager # Importa no shutdown para evitar circular

    logger.info("Iniciando processo de shutdown do serviço...")
    # Verifica se a classe DatabaseManager foi inicializada e se o pool existe
    if hasattr(DatabaseManager, '_instance') and DatabaseManager._instance._connection_pool:
        try:
            DatabaseManager._instance._connection_pool.closeall()
            logger.info("Pool de conexões PostgreSQL fechado.")
        except Exception as e:
            logger.error(f"Erro ao fechar o pool de conexões PostgreSQL: {e}", exc_info=True)
    else:
        logger.info("Nenhum pool de conexões ativo para fechar.")