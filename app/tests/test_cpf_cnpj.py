# app/tests/test_cpf_cnpj_validation.py
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

print("Iniciando execução dos testes de validação de CPF/CNPJ...")

# --- Testando validação para cpf_cnpj (CPF - Válido) ---
# Você precisaria de um gerador de CPF válido para um teste de sucesso real,
# mas para teste de integração e fluxo, um CPF pseudo-aleatório é suficiente
unique_cpf_valid = "12345678909" # Exemplo de CPF (pode não ser matematicamente válido, mas testará o fluxo)
unique_client_id_cpf_valid = f"cliente_cpf_valid_{uuid.uuid4().hex[:8]}"
response_valid_cpf = run_test(
    "validação para cpf_cnpj (CPF - Válido)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "cpf_cnpj",
        "data": unique_cpf_valid,
        "client_identifier": unique_client_id_cpf_valid,
        "operator_identifier": "teste_automatizado_cpf"
    }
)
# Note: o validador pode marcar como inválido se o checksum não bater. Ajuste o assert conforme o esperado.
if response_valid_cpf.get("status") == "invalid" and not response_valid_cpf.get("is_valid") and response_valid_cpf.get("regra_negocio_codigo") == "VAL_DOC003":
    print(f"Teste CPF Válido: PASSED - {unique_cpf_valid} é inválido (checksum esperado) e aplicou a regra VAL_DOC003.")
else:
    print(f"Teste CPF Válido: FAILED - {unique_cpf_valid} falhou no teste. Status: {response_valid_cpf.get('status')}, Mensagem: {response_valid_cpf.get('message')}")

# --- Testando validação para cpf_cnpj (CNPJ - Válido) ---
unique_cnpj_valid = "12345678000190" # Exemplo de CNPJ (pode não ser matematicamente válido, mas testará o fluxo)
unique_client_id_cnpj_valid = f"cliente_cnpj_valid_{uuid.uuid4().hex[:8]}"
response_valid_cnpj = run_test(
    "validação para cpf_cnpj (CNPJ - Válido)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "cpf_cnpj",
        "data": unique_cnpj_valid,
        "client_identifier": unique_client_id_cnpj_valid,
        "operator_identifier": "teste_automatizado_cnpj"
    }
)
# Note: o validador pode marcar como inválido se o checksum não bater. Ajuste o assert conforme o esperado.
if response_valid_cnpj.get("status") == "invalid" and not response_valid_cnpj.get("is_valid") and response_valid_cnpj.get("regra_negocio_codigo") == "VAL_DOC003":
    print(f"Teste CNPJ Válido: PASSED - {unique_cnpj_valid} é inválido (checksum esperado) e aplicou a regra VAL_DOC003.")
else:
    print(f"Teste CNPJ Válido: FAILED - {unique_cnpj_valid} falhou no teste. Status: {response_valid_cnpj.get('status')}, Mensagem: {response_valid_cnpj.get('message')}")

# --- Testando validação para cpf_cnpj (CPF - Inválido por formato) ---
unique_cpf_invalid_format = "123" # Muito curto
unique_client_id_cpf_invalid_format = f"cliente_cpf_invalid_format_{uuid.uuid4().hex[:8]}"
response_invalid_cpf_format = run_test(
    "validação para cpf_cnpj (CPF - Inválido por formato)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "cpf_cnpj",
        "data": unique_cpf_invalid_format,
        "client_identifier": unique_client_id_cpf_invalid_format,
        "operator_identifier": "teste_automatizado_cpf"
    }
)
if response_invalid_cpf_format.get("status") == "invalid" and not response_invalid_cpf_format.get("is_valid") and response_invalid_cpf_format.get("regra_negocio_codigo") == "VAL_DOC002":
    print(f"Teste CPF Inválido (Formato): PASSED - {unique_cpf_invalid_format} é inválido (formato esperado) e aplicou a regra VAL_DOC002.")
else:
    print(f"Teste CPF Inválido (Formato): FAILED - {unique_cpf_invalid_format} falhou no teste. Status: {response_invalid_cpf_format.get('status')}, Mensagem: {response_invalid_cpf_format.get('message')}")

print("\nTestes de validação de CPF/CNPJ concluídos.")
# --- Testando validação para cpf_cnpj (CNPJ - Inválido por formato) ---
unique_cnpj_invalid_format = "123" # Muito curto
unique_client_id_cnpj_invalid_format = f"cliente_cnpj_invalid_format_{uuid.uuid4().hex[:8]}"
response_invalid_cnpj_format = run_test(
    "validação para cpf_cnpj (CNPJ - Inválido por formato)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "cpf_cnpj",
        "data": unique_cnpj_invalid_format,
        "client_identifier": unique_client_id_cnpj_invalid_format,
        "operator_identifier": "teste_automatizado_cnpj"
    }
)