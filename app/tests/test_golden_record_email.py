# app/tests/test_golden_record_email.py
import requests
import json
import uuid # Para gerar IDs únicos
import time # Para adicionar um pequeno delay se necessário
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

print("Iniciando execução dos testes de Golden Record para Email...")

# --- Testando a eleição de Golden Record para um email ---
gr_email_data = "golden.record.test.valid@gmail.com" 

# Primeiro registro (deve se tornar o GR inicial)
initial_gr_client_id = f"gr_client_1_{uuid.uuid4().hex[:8]}"
print("\n--- Inserindo o primeiro registro para Golden Record ---")
response_1_gr = run_test(
    "Golden Record - Inserção Inicial",
    "/api/v1/validate",
    "POST",
    data={
        "type": "email",
        "data": gr_email_data,
        "client_identifier": initial_gr_client_id,
        "operator_identifier": "gr_test_operator_1"
    }
)

initial_gr_id = response_1_gr.get("record_id")
initial_gr_is_golden = response_1_gr.get("is_golden_record_for_this_transaction")
initial_gr_golden_id = response_1_gr.get("golden_record_id_for_normalized_data")

print(f"Status do 1º registro GR: is_golden_record_for_this_transaction={initial_gr_is_golden}, golden_record_id_for_normalized_data={initial_gr_golden_id}")
if initial_gr_is_golden and initial_gr_golden_id == initial_gr_id:
    print("Teste GR 1 (Inicial): PASSED - Primeiro registro se tornou o GR.")
else:
    print(f"Teste GR 1 (Inicial): FAILED - Primeiro registro NÃO se tornou o GR. Status: {initial_gr_is_golden}, Golden ID: {initial_gr_golden_id}, Record ID: {initial_gr_id}")


# Segundo registro (deve tentar se tornar o GR, se a pontuação for maior ou igual e for mais recente)
time.sleep(1) # Pequeno delay para garantir que created_at seja diferente, favorecendo nova eleição

second_gr_client_id = f"gr_client_2_{uuid.uuid4().hex[:8]}"
print("\n--- Inserindo o segundo registro para Golden Record ---")
response_2_gr = run_test(
    "Golden Record - Inserção de Atualização",
    "/api/v1/validate",
    "POST",
    data={
        "type": "email",
        "data": gr_email_data, # Mesmo dado para o GR
        "client_identifier": second_gr_client_id,
        "operator_identifier": "gr_test_operator_2"
    }
)

second_gr_id = response_2_gr.get("record_id")
second_gr_is_golden = response_2_gr.get("is_golden_record_for_this_transaction")
second_gr_golden_id = response_2_gr.get("golden_record_id_for_normalized_data")

print(f"Status do 2º registro GR: is_golden_record_for_this_transaction={second_gr_is_golden}, golden_record_id_for_normalized_data={second_gr_golden_id}")
if second_gr_is_golden and second_gr_golden_id == second_gr_id:
    print("Teste GR 2 (Atualização): PASSED - Segundo registro se tornou o GR.")
elif not second_gr_is_golden and str(second_gr_golden_id) == str(initial_gr_id):
    print("Teste GR 2 (Atualização): PASSED - Segundo registro não se tornou GR, mas GR ainda aponta para o primeiro. (Comportamento esperado se o score não for superior).")
else:
    print(f"Teste GR 2 (Atualização): FAILED - GR não se comportou como esperado. Status: {second_gr_is_golden}, Golden ID: {second_gr_golden_id}, Record ID: {second_gr_id}")


# --- Verificação final do Golden Record através do histórico ---
print("\n--- Verificando o Golden Record no histórico ---")
history_response_gr = run_test(
    "Obter Histórico para GR",
    f"/api/v1/history",
    "GET",
    params={"limit": 10, "include_deleted": False}
)

found_gr_in_history = False
if history_response_gr and history_response_gr.get("status") == "success":
    for record in history_response_gr.get("data", []):
        if record.get("dado_normalizado") == gr_email_data:
            # Verifica se is_golden_record é True ou se golden_record_id_for_normalized_data aponta para um dos IDs
            if record.get("is_golden_record") or str(record.get("golden_record_id_for_normalized_data")) in [str(initial_gr_id), str(second_gr_id)]:
                print(f"Found Golden Record related record for {gr_email_data}: ID {record.get('record_id')}, is_golden_record={record.get('is_golden_record')}, golden_record_id_for_normalized_data={record.get('golden_record_id_for_normalized_data')}")
                found_gr_in_history = True
else:
    print(f"Erro ao obter histórico para GR: {history_response_gr.get('message', 'Nenhuma mensagem de erro.')}")


if found_gr_in_history:
    print("Teste GR 3 (Histórico): PASSED - Registro relacionado ao Golden Record para 'golden.record.test.valid@gmail.com' encontrado no histórico.")
else:
    print("Teste GR 3 (Histórico): FAILED - Registro relacionado ao Golden Record para 'golden.record.test.valid@gmail.com' não encontrado no histórico.")

print("\nTestes de Golden Record para Email concluídos.")
