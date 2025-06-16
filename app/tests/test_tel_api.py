import pytest
import requests
import os
import sys

# **IMPORTANTE: Configure a URL base da sua API aqui**
# Se sua API estiver rodando localmente, por exemplo, na porta 5000
BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000/api") 
# Adicione a raiz do projeto ao sys.path para que `app.rules` seja encontrado
# Isso é crucial se você ainda estiver tendo problemas de importação com pytest
# Remova se conseguir resolver o problema de sys.path do pytest de forma mais limpa (e.g., via conftest.py)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"\n[DEBUG] Adicionado '{project_root}' ao sys.path para test_phone_api.py.\n")

@pytest.fixture(scope="module")
def api_base_url():
    """Fixture para fornecer a URL base da API."""
    return BASE_URL

def test_validate_phone_valid_br(api_base_url):
    """
    Testa a validação de um número de telefone brasileiro válido via API.
    """
    endpoint = f"{api_base_url}/validate/phone"
    payload = {
        "phone_number": "11987654321",
        "country_code_hint": "BR"
    }
    headers = {"Content-Type": "application/json"}

    print(f"\n[INFO] Testando POST {endpoint} com payload: {payload}")
    response = requests.post(endpoint, json=payload, headers=headers)
    
    print(f"[INFO] Status Code: {response.status_code}")
    print(f"[INFO] Response JSON: {response.json()}")

    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["cleaned_data"] == "+5511987654321"
    assert data["validation_code"] == "VAL_PHN001" # Ou VAL_PHN010 se phonenumbers está desativado na API

def test_validate_phone_invalid_format(api_base_url):
    """
    Testa a validação de um número de telefone com formato inválido via API.
    """
    endpoint = f"{api_base_url}/validate/phone"
    payload = {
        "phone_number": "12345", # Número muito curto
        "country_code_hint": "BR"
    }
    headers = {"Content-Type": "application/json"}

    print(f"\n[INFO] Testando POST {endpoint} com payload: {payload}")
    response = requests.post(endpoint, json=payload, headers=headers)
    
    print(f"[INFO] Status Code: {response.status_code}")
    print(f"[INFO] Response JSON: {response.json()}")

    assert response.status_code == 200 # A API deve retornar 200 com is_valid=False para validação de negócio
    data = response.json()
    assert data["is_valid"] is False
    assert data["validation_code"] in ["VAL_PHN002", "VAL_PHN012", "VAL_PHN020"] # Depende do fallback da sua API

def test_validate_phone_missing_param(api_base_url):
    """
    Testa a validação com parâmetro 'phone_number' ausente.
    Espera-se um erro 400 da API.
    """
    endpoint = f"{api_base_url}/validate/phone"
    payload = {
        "country_code_hint": "BR"
    }
    headers = {"Content-Type": "application/json"}

    print(f"\n[INFO] Testando POST {endpoint} com payload: {payload}")
    response = requests.post(endpoint, json=payload, headers=headers)
    
    print(f"[INFO] Status Code: {response.status_code}")
    print(f"[INFO] Response JSON: {response.json()}")

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "Parâmetro 'phone_number' é obrigatório" in data["error"]

def test_validate_phone_non_json_request(api_base_url):
    """
    Testa a validação com corpo da requisição não-JSON.
    Espera-se um erro 400 da API.
    """
    endpoint = f"{api_base_url}/validate/phone"
    payload = "isto não é json"
    headers = {"Content-Type": "text/plain"} # Content-Type incorreto

    print(f"\n[INFO] Testando POST {endpoint} com payload: '{payload}'")
    response = requests.post(endpoint, data=payload, headers=headers)
    
    print(f"[INFO] Status Code: {response.status_code}")
    print(f"[INFO] Response JSON: {response.text}") # Usar .text pois pode não ser JSON

    assert response.status_code == 400
    assert "Requisição deve ser JSON" in response.text # ou response.json()["error"] se sua API sempre retorna JSON