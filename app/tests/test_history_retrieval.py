# app/tests/test_history_retrieval.py
import requests
import json
import uuid
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

print("Iniciando execução dos testes de recuperação de histórico...")

# --- Testando histórico (limite=5, deletados=False) ---
response_history_5 = run_test(
    "histórico (limite=5, deletados=False)",
    "/api/v1/history",
    "GET",
    params={"limit": 5, "include_deleted": False}
)
if response_history_5.get("status") == "success" and len(response_history_5.get("data", [])) <= 5:
    print(f"Teste Histórico (limite=5, deletados=False): PASSED - {len(response_history_5.get('data', []))} registros recuperados.")
else:
    print(f"Teste Histórico (limite=5, deletados=False): FAILED - Não foi possível recuperar o histórico ou o limite está incorreto. Status: {response_history_5.get('status')}")

# --- Testando histórico (limite=10, deletados=True) ---
response_history_10_deleted = run_test(
    "histórico (limite=10, deletados=True)",
    "/api/v1/history",
    "GET",
    params={"limit": 10, "include_deleted": True}
)
if response_history_10_deleted.get("status") == "success" and len(response_history_10_deleted.get("data", [])) <= 10:
    print(f"Teste Histórico (limite=10, deletados=True): PASSED - {len(response_history_10_deleted.get('data', []))} registros recuperados (incluindo deletados).")
else:
    print(f"Teste Histórico (limite=10, deletados=True): FAILED - Não foi possível recuperar o histórico ou o limite está incorreto. Status: {response_history_10_deleted.get('status')}")

print("\nTestes de recuperação de histórico concluídos.")
# --- Testando histórico com filtro por client_identifier ---
unique_client_id = f"client_history_test_{uuid.uuid4().hex[:8]}"
response_history_client = run_test(
    "histórico por client_identifier",
    "/api/v1/history",
    "GET",
    params={"client_identifier": unique_client_id, "limit": 5, "include_deleted": False}
)