# app/tests/test_api.py
import requests
import json
import logging
from typing import Dict, Any, Optional 

# Configuração de logging para os testes
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# URL base da sua API
BASE_URL = "http://127.0.0.1:8001/api/v1"

# Chave de API para testes (deve corresponder a uma chave configurada em api_keys.json)
TEST_API_KEY = "API_KEY_PSDC" # Exemplo: uma chave com permissões de teste
HEADERS = {"X-API-KEY": TEST_API_KEY, "Content-Type": "application/json"}

def run_test(name: str, endpoint: str, method: str, payload: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None):
    """
    Função auxiliar para executar um teste de API e imprimir os resultados.
    """
    print(f"\n--- Testando {name} ---")
    try:
        if method == "POST":
            response = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload)
        elif method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params)
        elif method == "DELETE":
            response = requests.delete(f"{BASE_URL}{endpoint}", headers=HEADERS)
        else:
            print(f"Método HTTP '{method}' não suportado na função de teste.")
            return

        print(f"Status Code: {response.status_code}")

        try:
            response_json = response.json()
            print(f"Response JSON: {json.dumps(response_json, indent=2)}")
        except json.JSONDecodeError:
            print(f"Erro ao decodificar JSON na resposta: {response.text}")
            logger.error(f"Erro ao decodificar JSON na resposta do {name}: {response.text}", exc_info=True)
        
    except requests.exceptions.ConnectionError as e:
        print(f"Erro de conexão: Certifique-se de que o servidor FastAPI está rodando em {BASE_URL}. Erro: {e}")
        logger.error(f"Erro de conexão no teste '{name}': {e}", exc_info=True)
    except Exception as e:
        print(f"Erro inesperado na requisição de {name}: {e}")
        logger.error(f"Erro inesperado na requisição de {name}: {e}", exc_info=True)
    print("-" * 40)


if __name__ == "__main__":
    logger.info("Iniciando execução dos testes da API...")

    # Teste de Validação de Telefone (INVÁLIDO: sequencial/repetido)
    phone_payload_invalid = {
        "type": "telefone", # CORRIGIDO: de validation_type para type
        "data": "+5511987654321", # CORRIGIDO: dado como string direta
        "client_identifier": "cliente_python_001",
        "operator_identifier": "teste_automatizado" # CORRIGIDO: de operator_id para operator_identifier
    }
    run_test("validação para telefone", "/validate", "POST", phone_payload_invalid)

    # Teste de Validação de CPF (INVÁLIDO: dígito verificador)
    cpf_payload_invalid = {
        "type": "cpf_cnpj", # CORRIGIDO: de validation_type para type
        "data": "11122233344", # CORRIGIDO: dado como string direta
        "client_identifier": "cliente_python_002",
        "operator_identifier": "teste_automatizado_cpf", # CORRIGIDO: de operator_id para operator_identifier
        "cclub": "APP-FINANCAS-A" # Adicionado cclub no nível superior do payload
    }
    run_test("validação para cpf_cnpj", "/validate", "POST", cpf_payload_invalid)

    # Teste de Validação de CNPJ (INVÁLIDO: dígito verificador)
    cnpj_payload_invalid = {
        "type": "cpf_cnpj", # CORRIGIDO: de validation_type para type
        "data": "12345678000190", # CORRIGIDO: dado como string direta
        "client_identifier": "cliente_python_003",
        "operator_identifier": "teste_automatizado_cnpj", # CORRIGIDO: de operator_id para operator_identifier
        "cpssoa": "APP-VENDAS-B" # Adicionado cpssoa no nível superior do payload
    }
    run_test("validação para cpf_cnpj", "/validate", "POST", cnpj_payload_invalid)

    # Teste de Validação de Email (INVÁLIDO: domínio não aceita e-mail)
    email_payload_invalid = {
        "type": "email", # CORRIGIDO: de validation_type para type
        "data": "test@example.com", # CORRIGIDO: dado como string direta
        "client_identifier": "cliente_python_004",
        "operator_identifier": "teste_automatizado_email" # CORRIGIDO: de operator_id para operator_identifier
    }
    run_test("validação para email", "/validate", "POST", email_payload_invalid)

    # Teste de Validação de Endereço (VÁLIDO)
    address_payload_valid = {
        "type": "endereco", # CORRIGIDO: de validation_type para type
        "data": { # Este formato de dicionário para 'data' está correto para 'endereco'
            "cep": "01001000",
            "logradouro": "Praça da Sé",
            "numero": "1",
            "bairro": "Sé"
        },
        "client_identifier": "cliente_python_005",
        "operator_identifier": "teste_automatizado_endereco" # CORRIGIDO: de operator_id para operator_identifier
    }
    run_test("validação para endereco", "/validate", "POST", address_payload_valid)
    
    # Teste de Histórico
    history_params = {"limit": 5, "include_deleted": False}
    run_test("histórico (limite=5, deletados=False)", "/history", "GET", params=history_params)

    logger.info("Todos os testes concluídos.")
