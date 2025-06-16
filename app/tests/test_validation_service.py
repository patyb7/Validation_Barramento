# test_phone_validator.py

import pytest
from app.rules.phone.validator import PhoneValidator
from app.rules.phone.validator import (VAL_PHN001, VAL_PHN002, VAL_PHN003, VAL_PHN004, VAL_PHN005, VAL_PHN006,
    VAL_PHN010, VAL_PHN011, VAL_PHN012, VAL_PHN013, VAL_PHN014, VAL_PHN015,
    VAL_PHN016, VAL_PHN020, PHONENUMBERS_AVAILABLE
)

@pytest.fixture
def phone_validator():
    return PhoneValidator()

@pytest.mark.asyncio
async def test_valid_brazilian_mobile_number(phone_validator):
    """Testa um número de celular brasileiro válido com e sem phonenumbers."""
    phone_number = "11983802243"
    country_hint = "BR"
    result = await phone_validator.validate_phone(phone_number, country_hint)

    assert result["is_valid"] is True
    # Cleaned data deve ser E.164 formatado
    assert result["cleaned_data"] == "+5511983802243"
    assert "válido" in result["message"]
    # Verifica o código de validação correto dependendo da disponibilidade de phonenumbers
    expected_validation_code = VAL_PHN001 if PHONENUMBERS_AVAILABLE else VAL_PHN010
    expected_source = "phonenumbers" if PHONENUMBERS_AVAILABLE else "fallback"
    assert result["validation_code"] == expected_validation_code
    assert result["source"] == expected_source
    assert result["details"]["country_code_detected"] == 55 # Código do país deve ser 55 para BR
    assert result["details"]["national_number"] == 11983802243


@pytest.mark.asyncio
async def test_valid_brazilian_landline_number(phone_validator):
    """Testa um número fixo brasileiro válido."""
    phone_number = "2130001234" # Exemplo de número fixo
    country_hint = "BR"
    result = await phone_validator.validate_phone(phone_number, country_hint)

    assert result["is_valid"] is True
    assert result["cleaned_data"] == "+552130001234" # Espera formato E.164
    assert "válido" in result["message"]
    expected_validation_code = VAL_PHN001 if PHONENUMBERS_AVAILABLE else VAL_PHN010
    expected_source = "phonenumbers" if PHONENUMBERS_AVAILABLE else "fallback"
    assert result["validation_code"] == expected_validation_code
    assert result["source"] == expected_source
    assert result["details"]["country_code_detected"] == 55
    assert result["details"]["national_number"] == 2130001234

@pytest.mark.asyncio
async def test_invalid_brazilian_mobile_number(phone_validator):
    """Testa um número de celular brasileiro inválido (comprimento)."""
    phone_number = "1198380224" # Um dígito a menos
    country_hint = "BR"
    result = await phone_validator.validate_phone(phone_number, country_hint)

    assert result["is_valid"] is False
    assert result["validation_code"] == (VAL_PHN002 if PHONENUMBERS_AVAILABLE else VAL_PHN012)
    assert result["source"] == ("phonenumbers" if PHONENUMBERS_AVAILABLE else "fallback")
    assert "inválido" in result["message"] or "comprimento" in result["message"]

@pytest.mark.asyncio
async def test_invalid_brazilian_ddd(phone_validator):
    """Testa um número brasileiro com DDD inválido."""
    phone_number = "00983802243"
    country_hint = "BR"
    result = await phone_validator.validate_phone(phone_number, country_hint)

    assert result["is_valid"] is False
    # phonenumbers pode dar 00 como inválido ou parsing error. Fallback é VAL_PHN011.
    expected_validation_code = VAL_PHN002 if PHONENUMBERS_AVAILABLE else VAL_PHN011
    assert result["validation_code"] == expected_validation_code
    assert "inválido" in result["message"] or "erro de parsing" in result["message"]

@pytest.mark.asyncio
async def test_short_invalid_number(phone_validator):
    """Testa um número muito curto e inválido."""
    phone_number = "123"
    result = await phone_validator.validate_phone(phone_number)

    assert result["is_valid"] is False
    # Ajuste para verificar o código de validação específico
    assert result["validation_code"] == VAL_PHN020 # Ou VAL_PHN016 se fosse um número de serviço
    assert "não reconhecido" in result["message"] or "inválido" in result["message"]

@pytest.mark.asyncio
async def test_empty_string(phone_validator):
    """Testa com string vazia."""
    phone_number = ""
    result = await phone_validator.validate_phone(phone_number)

    assert result["is_valid"] is False
    assert result["validation_code"] == VAL_PHN003
    assert "vazia" in result["message"]

@pytest.mark.asyncio
async def test_none_input(phone_validator):
    """Testa com input None."""
    phone_number = None
    result = await phone_validator.validate_phone(phone_number)

    assert result["is_valid"] is False
    assert result["validation_code"] == VAL_PHN003
    assert "não vazia" in result["message"]

@pytest.mark.asyncio
async def test_non_string_input(phone_validator):
    """Testa com input não-string."""
    phone_number = 123456789
    result = await phone_validator.validate_phone(phone_number)

    assert result["is_valid"] is False
    assert result["validation_code"] == VAL_PHN003
    assert "string" in result["message"]

@pytest.mark.asyncio
async def test_number_with_only_non_digits(phone_validator):
    """Testa um número contendo apenas caracteres não-dígitos."""
    phone_number = "abc-def"
    result = await phone_validator.validate_phone(phone_number)

    assert result["is_valid"] is False
    assert result["validation_code"] == VAL_PHN003
    assert "vazio após limpeza" in result["message"]

@pytest.mark.asyncio
async def test_international_number_us(phone_validator):
    """Testa um número internacional (EUA) com hint."""
    phone_number = "12125550100" # Exemplo: +1 212-555-0100
    country_hint = "US"
    result = await phone_validator.validate_phone(phone_number, country_hint)

    if PHONENUMBERS_AVAILABLE:
        assert result["is_valid"] is True
        assert result["cleaned_data"] == "+12125550100"
        assert result["validation_code"] == VAL_PHN001
        assert result["source"] == "phonenumbers"
        assert result["details"]["country_code_detected"] == 1
        assert result["details"]["national_number"] == 2125550100
    else:
        # Sem phonenumbers, o fallback tenta ser mais permissivo para E.164 ou similar
        assert result["is_valid"] is True
        assert result["cleaned_data"] == "+12125550100" # Deve normalizar para E.164
        assert result["validation_code"] == VAL_PHN014
        assert result["source"] == "fallback"
        assert result["details"]["country_code_detected"] == 1
        assert result["details"]["national_number"] == 2125550100


@pytest.mark.asyncio
async def test_international_number_e164_format(phone_validator):
    """Testa um número já em formato E.164."""
    phone_number = "+442071234567" # Exemplo: Reino Unido
    result = await phone_validator.validate_phone(phone_number)

    if PHONENUMBERS_AVAILABLE:
        assert result["is_valid"] is True
        assert result["cleaned_data"] == "+442071234567"
        assert result["validation_code"] == VAL_PHN001
        assert result["source"] == "phonenumbers"
        assert result["details"]["country_code_detected"] == 44
        assert result["details"]["national_number"] == 2071234567
    else:
        assert result["is_valid"] is True
        assert result["cleaned_data"] == "+442071234567"
        assert result["validation_code"] == VAL_PHN014
        assert result["source"] == "fallback"
        assert result["details"]["country_code_detected"] == 44
        assert result["details"]["national_number"] == 2071234567

@pytest.mark.asyncio
async def test_possible_but_not_valid_number(phone_validator):
    """Testa um número que phonenumbers considera 'possível' mas não 'válido'."""
    phone_number = "11999999990" # Ex: um número fictício, pode ser possível mas não um real
    country_hint = "BR"
    result = await phone_validator.validate_phone(phone_number, country_hint)

    if PHONENUMBERS_AVAILABLE:
        assert result["is_valid"] is False
        assert result["validation_code"] == VAL_PHN004 # Possível, mas não válido
        assert result["source"] == "phonenumbers"
    else:
        assert result["is_valid"] is False # Fallback não tem distinção de 'possível' vs 'válido'
        assert result["validation_code"] == VAL_PHN012 # Cairá na regra de formato/comprimento BR inválido (se não for seq/repetido)
        assert result["source"] == "fallback"


@pytest.mark.asyncio
async def test_sequential_number(phone_validator):
    """Testa um número com dígitos sequenciais."""
    phone_number = "11123456789"
    result = await phone_validator.validate_phone(phone_number, "BR")

    assert result["is_valid"] is False
    assert result["validation_code"] == VAL_PHN013
    assert "sequencial" in result["message"]

@pytest.mark.asyncio
async def test_repeated_number(phone_validator):
    """Testa um número com dígitos repetidos."""
    phone_number = "11888888888"
    result = await phone_validator.validate_phone(phone_number, "BR")

    assert result["is_valid"] is False
    assert result["validation_code"] == VAL_PHN013
    assert "repetidos" in result["message"]

@pytest.mark.asyncio
async def test_number_with_non_digit_chars(phone_validator):
    """Testa um número com caracteres não-dígitos."""
    phone_number = "(11) 98380-2243"
    country_hint = "BR"
    result = await phone_validator.validate_phone(phone_number, country_hint)

    assert result["is_valid"] is True
    assert result["cleaned_data"] == "+5511983802243" # Deve limpar e normalizar
    assert "válido" in result["message"]
    expected_validation_code = VAL_PHN001 if PHONENUMBERS_AVAILABLE else VAL_PHN010
    assert result["validation_code"] == expected_validation_code
    assert result["details"]["country_code_detected"] == 55
    assert result["details"]["national_number"] == 11983802243

@pytest.mark.asyncio
async def test_international_number_invalid_length_fallback(phone_validator):
    """Testa um número internacional com comprimento inválido via fallback."""
    phone_number = "+12345" # Muito curto
    result = await phone_validator.validate_phone(phone_number)

    # Este teste é específico para o cenário de fallback quando phonenumbers NÃO está disponível
    # ou falhou. Se phonenumbers está disponível, ele deve ser a fonte primária.
    if PHONENUMBERS_AVAILABLE:
        # Se phonenumbers estiver disponível, ele deve marcar como inválido (VAL_PHN002)
        # ou parsing error (VAL_PHN005), e não cair no VAL_PHN015.
        assert result["is_valid"] is False
        assert result["source"] == "phonenumbers"
        assert result["validation_code"] in [VAL_PHN002, VAL_PHN005]
    else:
        assert result["is_valid"] is False
        assert result["validation_code"] == VAL_PHN015
        assert "comprimento de dígitos inválido" in result["message"]
        assert result["source"] == "fallback"

@pytest.mark.asyncio
async def test_brazilian_service_number(phone_validator):
    """Testa um número de serviço brasileiro válido."""
    phone_number = "190"
    result = await phone_validator.validate_phone(phone_number, "BR")

    assert result["is_valid"] is True
    assert result["cleaned_data"] == "190" # Não deve ser E.164, pois é um número de serviço curto
    assert result["validation_code"] == VAL_PHN016
    assert result["source"] == "fallback" # Normalmente tratado pelo fallback a menos que phonenumbers tenha tipo específico
    assert result["details"]["country_code_detected"] == 55 # Para o contexto BR
    assert result["details"]["national_number"] == 190
    assert "serviço/emergência" in result["message"]