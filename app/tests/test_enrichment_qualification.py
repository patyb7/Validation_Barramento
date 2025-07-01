# app/tests/test_enrichment_qualification.py
import requests
import random
import json
import uuid # Para gerar IDs únicos
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

print("Iniciando execução dos testes de Qualificação e Enriquecimento Simulados...")

# --- Teste de Qualificação e Enriquecimento Simulados (Email) ---
enriched_email_data = f"enriched.test.{uuid.uuid4().hex[:8]}@valid.com" # Use um domínio válido, pode ser simulado se não tiver um real
enriched_client_id = f"client_enriched_{uuid.uuid4().hex[:8]}"

response_enriched = run_test(
    "Validação e Enriquecimento (Email)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "email",
        "data": enriched_email_data,
        "client_identifier": enriched_client_id,
        "operator_identifier": "test_enrichment_operator"
    }
)

# Asserts para verificar os resultados de qualificação e enriquecimento
if response_enriched.get("status") == "success":
    print("Validação de Enriquecimento: STATUS SUCESSO.")
    # Verifica o status_qualificacao
    if response_enriched.get("status_qualificacao") == "QUALIFIED":
        print("Validação de Enriquecimento: PASSED - status_qualificacao é 'QUALIFIED'.")
    else:
        print(f"Validação de Enriquecimento: FAILED - status_qualificacao é '{response_enriched.get('status_qualificacao')}', esperado 'QUALIFIED'.")

    # Verifica o last_enrichment_attempt_at
    if response_enriched.get("last_enrichment_attempt_at"):
        print("Validação de Enriquecimento: PASSED - last_enrichment_attempt_at está presente.")
    else:
        print("Validação de Enriquecimento: FAILED - last_enrichment_attempt_at está ausente.")

    # Verifica se há dados enriquecidos nos detalhes de validação
    if response_enriched.get("validation_details", {}).get("enriched_data_example"):
        print("Validação de Enriquecimento: PASSED - Dados enriquecidos de exemplo encontrados em validation_details.")
        # Opcional: Verifique o conteúdo dos dados enriquecidos se tiver expectativas específicas
        enriched_data_content = response_enriched["validation_details"]["enriched_data_example"]
        if "source" in enriched_data_content and "confidence_score" in enriched_data_content:
            print("Validação de Enriquecimento: Dados enriquecidos contêm 'source' e 'confidence_score'.")
        else:
            print("Validação de Enriquecimento: Dados enriquecidos podem estar incompletos.")
    else:
        print("Validação de Enriquecimento: FAILED - Dados enriquecidos de exemplo ausentes em validation_details.")
else:
    print(f"Validação de Enriquecimento: FAILED - Validação de email falhou com status: {response_enriched.get('status')}")

print("\nTestes de Qualificação e Enriquecimento Simulados concluídos.")
# --- Teste de Qualificação e Enriquecimento Simulados (Telefone) ---
enriched_phone_data = f"+55119{random.randint(10000000, 99999999)}" # Use um número de telefone válido, pode ser simulado se não tiver um real
enriched_client_id_phone = f"client_enriched_phone_{uuid.uuid4().hex[:8]}"