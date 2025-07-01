# tests/test_full_pipeline.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta, timezone
import logging
from app.api.schemas.common import PersonDataModel, ValidationResult
# Importar classes do seu projeto
from app.rules.pessoa.composite_validator import PessoaFullValidacao
from app.rules.decision_rules import DecisionRules
from app.models.validation_record import ValidationRecord
from app.api.schemas.common import PersonDataModel, ValidationResult # Importe ValidationResult se for um modelo Pydantic

# Importar os mocks que você criou (assumindo que estão em tests/mocks.py)
from tests.mocks import (
    MockPhoneValidator,
    MockEmailValidator,
    MockCpfCnpjValidator,
    MockAddressValidator,
    MockNomeValidator,
    MockSexoValidator,
    MockRgValidator,
    MockDataNascimentoValidator,
    MockCepValidator,
    MockValidationRecordRepository,
    MockQualificationRepository,
    MockLogEntryRepository,
)

# Configuração para o logger para ver os logs durante o teste
logging.basicConfig(level=logging.INFO)

# --- FIXTURES ---

@pytest.fixture
def mock_validation_repo():
    return MockValidationRecordRepository()

@pytest.fixture
def mock_qualification_repo():
    return MockQualificationRepository()

@pytest.fixture
def mock_phone_validator():
    return MockPhoneValidator()

@pytest.fixture
def mock_email_validator():
    return MockEmailValidator()

@pytest.fixture
def mock_cpf_cnpj_validator():
    mock = AsyncMock()
    mock.validate.return_value = {
        "is_valid": True,
        "dado_original": "12345678900",
        "dado_normalizado": "12345678900",
        "mensagem": "CPF válido e encontrado.",
        "details": {},
        "business_rule_applied": {"code": "RN_DOC001", "type": "Documento", "name": "CPF Válido e Encontrado"}
    }
    return mock

@pytest.fixture
def mock_address_validator():
    mock = AsyncMock()
    mock.validate.return_value = {
        "is_valid": True,
        "dado_original": {"logradouro": "Rua Teste", "numero": "123"},
        "dado_normalizado": {"logradouro": "Rua Teste", "numero": "123", "bairro": "Centro", "cidade": "Cidade Teste", "estado": "SP", "cep": "12345678"},
        "mensagem": "Endereço válido e consistente.",
        "details": {"cep_validation": {"is_valid": True, "business_rule_applied": {"code": "RN_CEP001"}}},
        "business_rule_applied": {"code": "RN_ADDR001", "type": "Endereço", "name": "Endereço 100% Consistente"}
    }
    return mock

@pytest.fixture
def mock_nome_validator():
    mock = AsyncMock()
    mock.validate.return_value = {
        "is_valid": True,
        "dado_original": "João Silva",
        "dado_normalizado": "JOAO SILVA",
        "mensagem": "Nome válido.",
        "details": {},
        "business_rule_applied": {"code": "RN_NOM001", "type": "Nome", "name": "Nome Válido"}
    }
    return mock

@pytest.fixture
def mock_sexo_validator():
    mock = AsyncMock()
    mock.validate.return_value = {
        "is_valid": True,
        "dado_original": "M",
        "dado_normalizado": "MASCULINO",
        "mensagem": "Sexo válido.",
        "details": {},
        "business_rule_applied": {"code": "RN_SEX001", "type": "Sexo", "name": "Sexo Válido"}
    }
    return mock

@pytest.fixture
def mock_rg_validator():
    mock = AsyncMock()
    mock.validate.return_value = {
        "is_valid": True,
        "dado_original": "123456789",
        "dado_normalizado": "123456789",
        "mensagem": "RG válido e ativo.",
        "details": {},
        "business_rule_applied": {"code": "RN_RG001", "type": "Documento", "name": "RG Válido e Ativo"}
    }
    return mock

@pytest.fixture
def mock_data_nascimento_validator():
    mock = AsyncMock()
    mock.validate.return_value = {
        "is_valid": True,
        "dado_original": "1990-01-01",
        "dado_normalizado": "1990-01-01",
        "mensagem": "Data de nascimento válida.",
        "details": {},
        "business_rule_applied": {"code": "RN_DTN001", "type": "Data de Nascimento", "name": "Data de Nascimento Válida"}
    }
    return mock

@pytest.fixture
def mock_cep_validator():
    mock = AsyncMock()
    mock.validate.return_value = {
        "is_valid": True,
        "dado_original": "12345-678",
        "dado_normalizado": "12345678",
        "mensagem": "CEP válido.",
        "details": {},
        "business_rule_applied": {"code": "RN_CEP001", "type": "CEP", "name": "CEP Válido"}
    }
    return mock


@pytest.fixture
def pessoa_full_validator(
    mock_phone_validator,
    mock_cep_validator,
    mock_email_validator,
    mock_cpf_cnpj_validator,
    mock_address_validator,
    mock_nome_validator,
    mock_sexo_validator,
    mock_rg_validator,
    mock_data_nascimento_validator
):
    # Aqui, a instância de PessoaFullValidacao receberá os mocks como dependências
    return PessoaFullValidacao(
        phone_validator=mock_phone_validator,
        cep_validator=mock_cep_validator,
        email_validator=mock_email_validator,
        cpf_cnpj_validator=mock_cpf_cnpj_validator,
        address_validator=mock_address_validator,
        nome_validator=mock_nome_validator,
        sexo_validator=mock_sexo_validator,
        rg_validator=mock_rg_validator,
        data_nascimento_validator=mock_data_nascimento_validator
    )

@pytest.fixture
def decision_rules(mock_validation_repo, mock_qualification_repo):
    return DecisionRules(mock_validation_repo, mock_qualification_repo)
## Testes de Fluxo Completo
@pytest.mark.asyncio
async def test_golden_record_perfeito_flow(
    pessoa_full_validator, decision_rules, mock_validation_repo, mock_qualification_repo,
    mock_phone_validator, # Importante: injete o mock diretamente aqui para configurá-lo
    mock_email_validator,
    mock_cpf_cnpj_validator,
    mock_address_validator,
    mock_rg_validator
):
    """
    Testa um fluxo completo onde os dados são perfeitos e resultam em um Golden Record.
    """
    # 1. Dados de entrada simulados
    person_data = PersonDataModel(
        nome="Teste Golden",
        cpf="123.456.789-00",
        data_nascimento="1990-01-01",
        email="teste@golden.com",
        logradouro="Rua Perfeita",
        numero="100",
        bairro="Centro",
        cidade="Sao Paulo",
        estado="SP",
        cep="01000-000",
        celular="11987654321",
        telefone_fixo="1130001122",
        rg="123456789",
        sexo="MASCULINO"
    )
    app_info = {"source_app": "test_app", "process_id": "proc123"}
    client_identifier = "CLIENT_ABC"

    # Mocks para garantir que validadores retornam resultados "perfeitos"
    # Agora configuramos os mocks injetados diretamente
    mock_phone_validator.validate.side_effect = [
        {"is_valid": True, "dado_original": "11987654321", "dado_normalizado": "11987654321", "mensagem": "Telefone válido.", "details": {}, "business_rule_applied": {"code": "RN_TEL001", "type": "Telefone", "name": "Telefone Encontrado na Base"}},
        {"is_valid": True, "dado_original": "1130001122", "dado_normalizado": "1130001122", "mensagem": "Telefone válido.", "details": {}, "business_rule_applied": {"code": "RN_TEL001", "type": "Telefone", "name": "Telefone Encontrado na Base"}}
    ]
    # Usando return_value para outros mocks que não precisam de side_effect
    mock_email_validator.validate.return_value = {"is_valid": True, "dado_original": "teste@golden.com", "dado_normalizado": "teste@golden.com", "mensagem": "E-mail válido.", "details": {}, "business_rule_applied": {"code": "RN_EMAIL002", "type": "Email", "name": "Email Verificado"}}
    mock_cpf_cnpj_validator.validate.return_value = {"is_valid": True, "dado_original": "123.456.789-00", "dado_normalizado": "12345678900", "mensagem": "CPF válido e encontrado.", "details": {}, "business_rule_applied": {"code": "RN_DOC001", "type": "Documento", "name": "CPF Válido e Encontrado"}}
    mock_address_validator.validate.return_value = {"is_valid": True, "dado_original": {"logradouro": "Rua Perfeita", "numero": "100"}, "dado_normalizado": {"logradouro": "Rua Perfeita", "numero": "100", "bairro": "Centro", "cidade": "Sao Paulo", "estado": "SP", "cep": "01000000"}, "mensagem": "Endereço válido.", "details": {}, "business_rule_applied": {"code": "RN_ADDR001", "type": "Endereço", "name": "Endereço 100% Consistente"}}
    mock_rg_validator.validate.return_value = {"is_valid": True, "dado_original": "123456789", "dado_normalizado": "123456789", "mensagem": "RG válido e ativo.", "details": {}, "business_rule_applied": {"code": "RN_RG001", "type": "Documento", "name": "RG Válido e Ativo"}}


    # 2. Executar o validador composto
    validation_results_raw = await pessoa_full_validator.validate(person_data, client_identifier=client_identifier)
    # Converter o resultado para o modelo Pydantic ValidationResult para garantir consistência
    # Se 'validation_results' já for um modelo Pydantic, esta linha pode ser desnecessária
    validation_results = ValidationResult(**validation_results_raw)

    assert validation_results.is_valid is True
    assert validation_results.overall_message == "Todos os dados de pessoa válidos."
    assert "cpf" in validation_results.normalized_data
    assert validation_results.details.individual_validations["cpf"].business_rule_applied.code == "RN_DOC001"
    assert validation_results.details.individual_validations["celular"].business_rule_applied.code == "RN_TEL001"
    assert not validation_results.details.errors_summary # Nenhumm erro

    # 3. Criar o ValidationRecord inicial
    initial_record = ValidationRecord(
        client_identifier=client_identifier,
        tipo_validacao="pessoa_completa",
        app_info=app_info,
        validation_results=validation_results.model_dump(), # Use .model_dump() para Pydantic v2
        validation_details=validation_results.details.model_dump(), # Use .model_dump()
        is_golden_record=False, # Estado inicial
        status_qualificacao="PENDING_DECISION", # Estado inicial
        # Campos adicionais exigidos por ValidationRecord (verifique seu modelo)
        dado_original=person_data.model_dump_json(), # Ou PersonDataModel.model_dump()
        is_valido=validation_results.is_valid,
        mensagem=validation_results.overall_message,
        origem_validacao=app_info.get("source_app", "desconhecido"), # Use .get para segurança
        app_name=app_info.get("source_app", "desconhecido")
    )
    created_record = await mock_validation_repo.create_record(initial_record)
    assert created_record is not None
    assert created_record.status_qualificacao == "PENDING_DECISION"

    # 4. Aplicar as regras de decisão
    actions_summary = await decision_rules.apply_rules(created_record, app_info)

    # 5. Verificar o ValidationRecord atualizado no mock do repositório
    updated_record_data = await mock_validation_repo.get_record(created_record.id)

    assert updated_record_data["is_golden_record"] is True
    assert updated_record_data["status_qualificacao"] == "QUALIFIED"
    assert updated_record_data["golden_record_id"] is not None
    assert updated_record_data["unqualified_reasons"] == []

    # 6. Verificar a criação/atualização do Client Entity (Golden Record)
    gr_entity = await mock_qualification_repo.get_client_entity_by_main_document(updated_record_data["validation_results"]["normalized_data"]["cpf"])
    assert gr_entity is not None
    assert gr_entity["main_document_normalized"] == updated_record_data["validation_results"]["normalized_data"]["cpf"]
    assert gr_entity["consolidated_data"]["celular"] == "11987654321"
    assert gr_entity["golden_record_cpf_cnpj_id"] == str(updated_record_data["id"])
    assert gr_entity["golden_record_celular_id"] == str(updated_record_data["id"])
    assert gr_entity["golden_record_endereco_id"] == str(updated_record_data["id"])
    assert gr_entity["golden_record_cep_from_address_id"] == str(updated_record_data["id"])
    assert actions_summary["client_entity_created_or_updated"] is True
    assert actions_summary["status_qualificacao_set"] == "QUALIFIED"
    assert actions_summary["is_golden_record_candidate"] is True


@pytest.mark.asyncio
async def test_pending_revalidation_flow(
    pessoa_full_validator, decision_rules, mock_validation_repo, mock_qualification_repo,
    mock_phone_validator # Reutiliza o mock, mas ajusta comportamento
):
    """
    Testa o fluxo onde o celular tem RN_TEL004, resultando em PENDING_REVALIDATION.
    """
    # Ajusta o mock do telefone para simular RN_TEL004
    mock_phone_validator.validate.side_effect = [
        {"is_valid": True, "dado_original": "11999999999", "dado_normalizado": "11999999999", "mensagem": "Telefone válido (formato), mas não encontrado na base cadastral simulada.", "details": {}, "business_rule_applied": {"code": "RN_TEL004", "type": "Telefone", "name": "Telefone Válido (Formato) - Não Encontrado"}},
        {"is_valid": True, "dado_original": "1130001122", "dado_normalizado": "1130001122", "mensagem": "Telefone válido.", "details": {}, "business_rule_applied": {"code": "RN_TEL001", "type": "Telefone", "name": "Telefone Encontrado na Base"}}
    ]
    
    # 1. Dados de entrada simulados (restante perfeito, celular com RN_TEL004)
    person_data = PersonDataModel(
        nome="Teste Revalidar",
        cpf="098.765.432-10",
        data_nascimento="1985-05-10",
        email="revalidar@exemplo.com",
        logradouro="Rua Pendente",
        numero="200",
        bairro="Jardim",
        cidade="Sao Paulo",
        estado="SP",
        cep="02000-000",
        celular="11999999999", # Este será o RN_TEL004
        telefone_fixo="1130001122",
        rg="987654321",
        sexo="FEMININO"
    )
    app_info = {"source_app": "test_reval", "process_id": "proc456"}
    client_identifier = "CLIENT_XYZ"

    # 2. Executar o validador composto
    validation_results_raw = await pessoa_full_validator.validate(person_data, client_identifier=client_identifier)
    validation_results = ValidationResult(**validation_results_raw)

    assert validation_results.is_valid is True # O validador composto ainda pode considerar válido no geral
    assert validation_results.details.individual_validations["celular"].business_rule_applied.code == "RN_TEL004"
    # Deve haver uma mensagem de erro no summary para o celular
    assert any("Celular" in msg for msg in validation_results.details.errors_summary)

    # 3. Criar o ValidationRecord inicial
    initial_record = ValidationRecord(
        client_identifier=client_identifier,
        tipo_validacao="pessoa_completa",
        app_info=app_info,
        validation_results=validation_results.model_dump(),
        validation_details=validation_results.details.model_dump(),
        is_golden_record=False,
        status_qualificacao="PENDING_DECISION",
        # Campos adicionais exigidos por ValidationRecord
        dado_original=person_data.model_dump_json(),
        is_valido=validation_results.is_valid,
        mensagem=validation_results.overall_message,
        origem_validacao=app_info.get("source_app", "desconhecido"),
        app_name=app_info.get("source_app", "desconhecido")
    )
    created_record = await mock_validation_repo.create_record(initial_record)

    # 4. Aplicar as regras de decisão
    actions_summary = await decision_rules.apply_rules(created_record, app_info)

    # 5. Verificar o ValidationRecord atualizado
    updated_record_data = await mock_validation_repo.get_record(created_record.id)

    assert updated_record_data["is_golden_record"] is False
    assert updated_record_data["status_qualificacao"] == "PENDING_REVALIDATION"
    assert updated_record_data["golden_record_id"] is None
    assert "celular_pending_revalidation" in updated_record_data["unqualified_reasons"] # Ou similar

    # 6. Verificar a criação da QualificacaoPendente
    assert actions_summary["moved_to_qualificacoes_pendentes_queue"] is True
    # mock_qualification_repo._pending_qualifications deve conter o registro
    found_pending = False
    for pq_id, pq_data in mock_qualification_repo._pending_qualifications.items():
        if pq_data["validation_record_id"] == str(updated_record_data["id"]):
            found_pending = True
            assert pq_data["status_motivo"] == "Celular válido (formato), mas não encontrado na base cadastral simulada. Revalidação agendada."
            assert pq_data["attempt_count"] == 0
            # Compare apenas as datas, ignore a hora exata devido a segundos de diferença
            assert pq_data["scheduled_next_attempt_at"].date() == (datetime.now(timezone.utc) + timedelta(days=1)).date()
            break
    assert found_pending, "Registro de qualificação pendente não foi encontrado."
    assert actions_summary["status_qualificacao_set"] == "PENDING_REVALIDATION"
    assert actions_summary["is_golden_record_candidate"] is False


@pytest.mark.asyncio
async def test_unqualified_flow(
    pessoa_full_validator, decision_rules, mock_validation_repo, mock_qualification_repo,
    mock_cpf_cnpj_validator # Injetado como mock
):
    """
    Testa o fluxo onde os dados são inválidos, resultando em UNQUALIFIED.
    """
    # Ajusta o mock do CPF para retornar inválido
    mock_cpf_cnpj_validator.validate.return_value = {
        "is_valid": False,
        "dado_original": "123.456.789-XX",
        "dado_normalizado": None,
        "mensagem": "CPF inválido ou não encontrado.",
        "details": {},
        "business_rule_applied": {"code": "RN_DOC000", "type": "Documento", "name": "CPF Inválido"}
    }

    # 1. Dados de entrada simulados (CPF inválido)
    person_data = PersonDataModel(
        nome="Teste Invalido",
        cpf="123.456.789-XX", # CPF inválido
        data_nascimento="2000-12-31",
        email="invalido@teste.com",
        logradouro="Rua Qualquer",
        numero="300",
        bairro="Centro",
        cidade="Cidade Inválida",
        estado="XX",
        cep="99999-999",
        celular="11911112222",
        telefone_fixo=None,
        rg="111222333",
        sexo="FEMININO"
    )
    app_info = {"source_app": "test_invalid", "process_id": "proc789"}
    client_identifier = "CLIENT_Z"

    # 2. Executar o validador composto
    validation_results_raw = await pessoa_full_validator.validate(person_data, client_identifier=client_identifier)
    validation_results = ValidationResult(**validation_results_raw)

    assert validation_results.is_valid is False
    assert validation_results.details.individual_validations["cpf"].is_valid is False
    assert any("CPF" in msg for msg in validation_results.details.errors_summary)

    # 3. Criar o ValidationRecord inicial
    initial_record = ValidationRecord(
        client_identifier=client_identifier,
        tipo_validacao="pessoa_completa",
        app_info=app_info,
        validation_results=validation_results.model_dump(),
        validation_details=validation_results.details.model_dump(),
        is_golden_record=False,
        status_qualificacao="PENDING_DECISION", # Vai ser alterado pelas regras de decisão
        # Campos adicionais exigidos por ValidationRecord
        dado_original=person_data.model_dump_json(),
        is_valido=validation_results.is_valid,
        mensagem=validation_results.overall_message,
        origem_validacao=app_info.get("source_app", "desconhecido"),
        app_name=app_info.get("source_app", "desconhecido")
    )
    created_record = await mock_validation_repo.create_record(initial_record)

    # 4. Aplicar as regras de decisão
    actions_summary = await decision_rules.apply_rules(created_record, app_info)

    # 5. Verificar o ValidationRecord atualizado
    updated_record_data = await mock_validation_repo.get_record(created_record.id)

    assert updated_record_data["is_golden_record"] is False
    assert updated_record_data["status_qualificacao"] == "UNQUALIFIED"
    assert updated_record_data["golden_record_id"] is None
    # A mensagem específica da regra deve estar aqui
    assert "Campo 'cpf' não atende à regra de negócio exigida (RN_DOC001)." in updated_record_data["unqualified_reasons"] # Ou a mensagem exata da RN_DOC000


    # 6. Verificar que nenhuma ClientEntity ou QualificacaoPendente foi criada
    # Acessar dados original do Pydantic Model ou usar uma versão segura
    try:
        cpf_original = person_data.cpf
    except AttributeError: # Se o campo não existir, use um valor padrão ou skip
        cpf_original = None # Ou ""
    
    gr_entity = await mock_qualification_repo.get_client_entity_by_main_document(cpf_original)
    assert gr_entity is None
    assert not mock_qualification_repo._pending_qualifications # Deve estar vazio para este caso
    assert actions_summary["client_entity_created_or_updated"] is False
    assert actions_summary["moved_to_qualificacoes_pendentes_queue"] is False
    assert actions_summary["status_qualificacao_set"] == "UNQUALIFIED"
    assert actions_summary["is_golden_record_candidate"] is False