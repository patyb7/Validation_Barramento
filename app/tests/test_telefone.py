# app/tests/test_phone_validation.py

"""Este arquivo contém os testes para a funcionalidade de validação de telefone"""
import requests
import json
import uuid # Para gerar IDs únicos
import random # Para gerar números aleatórios para dados de teste
from typing import Optional, Dict, Any

# Base URL da sua API
BASE_URL = "http://127.0.0.1:8001"
# Use a sua API Key real aqui. Certifique-se de que ela está ativa no api_keys.json
API_KEY_PSDC = "API_KEY_PSDC" # Substitua pela sua API Key do sistema PSDC

headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY_PSDC
}

def run_test(test_name: str, endpoint: str, method: str, data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Executa uma requisição HTTP para a API e imprime o status e a resposta.
    Retorna a resposta JSON parseada.
    """
    print(f"\n--- Testando {test_name} ---")
    response = requests.request(method, f"{BASE_URL}{endpoint}", headers=headers, json=data, params=params)
    print(f"Status Code: {response.status_code}")
    response_json: Dict[str, Any] = {}
    try:
        response_json = response.json()
        print(f"Response JSON: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
    except json.JSONDecodeError:
        print(f"Response Body (não JSON): {response.text}")
    print("----------------------------------------")
    return response_json

print("Iniciando execução dos testes de validação de telefone...")

# --- Testando validação para telefone (válido) ---
unique_phone_number_valid = f"+55119{random.randint(10000000, 99999999)}"
unique_client_id_phone_valid = f"cliente_phone_valid_{uuid.uuid4().hex[:8]}"
response_valid_phone = run_test(
    "validação para telefone (válido)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "telefone",
        "data": unique_phone_number_valid,
        "client_identifier": unique_client_id_phone_valid,
        "operator_identifier": "teste_automatizado"
    }
)
if response_valid_phone.get("status") == "success" and response_valid_phone.get("is_valid"):
    print(f"Teste Telefone Válido: PASSED - {unique_phone_number_valid} é válido.")
else:
    print(f"Teste Telefone Válido: FAILED - {unique_phone_number_valid} não é válido. Mensagem: {response_valid_phone.get('message')}")


# --- Testando um telefone inválido (sequencial) para verificar a regra RNT_PHN013 ---
unique_phone_number_invalid_sequential = f"+5511987654321" # Exemplo de número sequencial
unique_client_id_phone_invalid_sequential = f"cliente_phone_invalid_sequential_{uuid.uuid4().hex[:8]}"
response_invalid_phone_sequential = run_test(
    "validação para telefone (inválido - sequencial)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "telefone",
        "data": unique_phone_number_invalid_sequential,
        "client_identifier": unique_client_id_phone_invalid_sequential,
        "operator_identifier": "teste_automatizado"
    }
)
if response_invalid_phone_sequential.get("status") == "invalid" and not response_invalid_phone_sequential.get("is_valid") and response_invalid_phone_sequential.get("regra_negocio_codigo") == "RNT_PHN013":
    print(f"Teste Telefone Inválido (Sequencial): PASSED - {unique_phone_number_invalid_sequential} é inválido e aplicou a regra RNT_PHN013.")
else:
    print(f"Teste Telefone Inválido (Sequencial): FAILED - {unique_phone_number_invalid_sequential} é válido ou não aplicou a regra RNT_PHN013. Status: {response_invalid_phone_sequential.get('status')}, Mensagem: {response_invalid_phone_sequential.get('message')}, Regra: {response_invalid_phone_sequential.get('regra_negocio_codigo')}")

# --- Testando um telefone inválido (comprimento) ---
unique_phone_number_invalid_length = f"+55119123" # Muito curto
unique_client_id_phone_invalid_length = f"cliente_phone_invalid_length_{uuid.uuid4().hex[:8]}"
response_invalid_phone_length = run_test(
    "validação para telefone (inválido - comprimento)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "telefone",
        "data": unique_phone_number_invalid_length,
        "client_identifier": unique_client_id_phone_invalid_length,
        "operator_identifier": "teste_automatizado"
    }
)
if response_invalid_phone_length.get("status") == "invalid" and not response_invalid_phone_length.get("is_valid") and response_invalid_phone_length.get("regra_negocio_codigo") == "RNT_PHN012":
    print(f"Teste Telefone Inválido (Comprimento): PASSED - {unique_phone_number_invalid_length} é inválido e aplicou a regra RNT_PHN012.")
else:
    print(f"Teste Telefone Inválido (Comprimento): FAILED - {unique_phone_number_invalid_length} é válido ou não aplicou a regra RNT_PHN012. Status: {response_invalid_phone_length.get('status')}, Mensagem: {response_invalid_phone_length.get('message')}, Regra: {response_invalid_phone_length.get('regra_negocio_codigo')}")

print("\nTestes de validação de telefone concluídos.")
