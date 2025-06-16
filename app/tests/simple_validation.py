import pytest
import asyncio
import sys # Adicione esta linha
import os  # Adicione esta linha

print("\n--- sys.path no test_phone_validator_simple.py ---")
for p in sys.path:
    print(p)
print(f"--- os.getcwd() no test_phone_validator_simple.py: {os.getcwd()} ---\n")

from app.rules.phone.validator import PhoneValidator

@pytest.mark.asyncio
async def test_validator_instantiation_and_basic_validation():
    """
    Testa se o PhoneValidator pode ser instanciado
    e se uma validação básica retorna a estrutura esperada.
    """
    validator = PhoneValidator()
    assert validator is not None, "PhoneValidator deve ser instanciável."

    result = await validator.validate_phone("11987654321", "BR")

    assert isinstance(result, dict)
    assert "is_valid" in result
    assert "cleaned_data" in result
    assert "message" in result
    assert "source" in result
    assert "details" in result
    assert "validation_code" in result

    print(f"\nResultado da validação simples: {result}")