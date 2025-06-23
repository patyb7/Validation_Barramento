# app/tests/test_address_validation.py
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

print("Iniciando execução dos testes de validação de endereço...")

# --- Testando validação para endereco (válido) ---
unique_address_number_valid = random.randint(1, 9999)
unique_address_complement_valid = f"apto {random.randint(1, 999)}"
unique_client_id_address_valid = f"cliente_endereco_valid_{uuid.uuid4().hex[:8]}"
response_valid_address = run_test(
    "validação para endereco (válido)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "endereco",
        "data": {
            "cep": "01001000",
            "logradouro": "Praça da Sé",
            "numero": str(unique_address_number_valid),
            "bairro": "Sé",
            "cidade": "São Paulo",
            "estado": "SP",
            "complemento": unique_address_complement_valid
        },
        "client_identifier": unique_client_id_address_valid,
        "operator_identifier": "teste_automatizado_endereco"
    }
)
if response_valid_address.get("status") == "success" and response_valid_address.get("is_valid"):
    print(f"Teste Endereço Válido: PASSED - Endereço é válido.")
else:
    print(f"Teste Endereço Válido: FAILED - Endereço não é válido. Mensagem: {response_valid_address.get('message')}")

# --- Testando validação para endereco (inválido - CEP) ---
unique_address_number_invalid_cep = random.randint(1, 9999)
unique_client_id_address_invalid_cep = f"cliente_endereco_invalid_cep_{uuid.uuid4().hex[:8]}"
response_invalid_address_cep = run_test(
    "validação para endereco (inválido - CEP)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "endereco",
        "data": {
            "cep": "99999999", # CEP inválido
            "logradouro": "Rua Falsa",
            "numero": str(unique_address_number_invalid_cep),
            "bairro": "Bairro Falso",
            "cidade": "Cidade Falsa",
            "estado": "UF"
        },
        "client_identifier": unique_client_id_address_invalid_cep,
        "operator_identifier": "teste_automatizado_endereco"
    }
)
if response_invalid_address_cep.get("status") == "invalid" and not response_invalid_address_cep.get("is_valid") and "CEP inválido ou não encontrado" in response_invalid_address_cep.get("message", ""):
    print(f"Teste Endereço Inválido (CEP): PASSED - Endereço é inválido (CEP).")
else:
    print(f"Teste Endereço Inválido (CEP): FAILED - Endereço falhou no teste. Status: {response_invalid_address_cep.get('status')}, Mensagem: {response_invalid_address_cep.get('message')}")

print("\nTestes de validação de endereço concluídos.")
# --- Testando validação para endereco (inválido - número) ---
unique_address_number_invalid_number = "abc" # Número inválido
unique_client_id_address_invalid_number = f"cliente_endereco_invalid_number_{uuid.uuid4().hex[:8]}"
response_invalid_address_number = run_test(
    "validação para endereco (inválido - número)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "endereco",
        "data": {
            "cep": "01001000",
            "logradouro": "Praça da Sé",
            "numero": unique_address_number_invalid_number, # Número inválido
            "bairro": "Sé",
            "cidade": "São Paulo",
            "estado": "SP",
            "complemento": unique_address_complement_valid
        },
        "client_identifier": unique_client_id_address_invalid_number,
        "operator_identifier": "teste_automatizado_endereco"
    }
)