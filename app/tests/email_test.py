# app/tests/test_api.py
import requests
import json
import uuid # Para gerar IDs únicos
import random # Para gerar números aleatórios para dados de teste
import time # Para adicionar um pequeno delay se necessário
from typing import Optional, Dict, Any, Union

# Base URL da sua API
BASE_URL = "http://127.0.0.1:8001"
# Use a sua API Key real aqui. Certifique-se de que ela está ativa no api_keys.json
# Exemplo: "API_KEY_PSDC" se essa for a string literal da sua chave
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
    # Usa ensure_ascii=False para exibir caracteres especiais corretamente
    response_json: Dict[str, Any] = {}
    try:
        response_json = response.json()
        print(f"Response JSON: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
    except json.JSONDecodeError:
        print(f"Response Body (não JSON): {response.text}")
    print("----------------------------------------")
    return response_json

print("Iniciando execução dos testes da API...")

# --- Testando validação para telefone ---
# Gerar um dado de telefone único por execução
# Gerando um número válido para testar cenários de sucesso
unique_phone_number_valid = f"+55119{random.randint(10000000, 99999999)}"
unique_client_id_phone_valid = f"cliente_phone_valid_{uuid.uuid4().hex[:8]}"
run_test(
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

# Testando um telefone inválido (sequencial) para verificar a regra RNT_PHN013
unique_phone_number_invalid = f"+5511987654321" # Exemplo de número sequencial
unique_client_id_phone_invalid = f"cliente_phone_invalid_{uuid.uuid4().hex[:8]}"
run_test(
    "validação para telefone (inválido - sequencial)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "telefone",
        "data": unique_phone_number_invalid,
        "client_identifier": unique_client_id_phone_invalid,
        "operator_identifier": "teste_automatizado"
    }
)

# --- Testando validação para cpf_cnpj (CPF) ---
# Gerar um CPF pseudo-aleatório (pode não ser matematicamente válido, mas será único)
unique_cpf = f"{random.randint(10000000000, 99999999999)}"
unique_client_id_cpf = f"cliente_cpf_{uuid.uuid4().hex[:8]}"
run_test(
    "validação para cpf_cnpj (CPF)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "cpf_cnpj",
        "data": unique_cpf,
        "client_identifier": unique_client_id_cpf,
        "operator_identifier": "teste_automatizado_cpf"
    }
)

# --- Testando validação para cpf_cnpj (CNPJ) ---
# Gerar um CNPJ pseudo-aleatório (pode não ser matematicamente válido, mas será único)
unique_cnpj = f"{random.randint(10000000000000, 99999999999999)}"
unique_client_id_cnpj = f"cliente_cnpj_{uuid.uuid4().hex[:8]}"
run_test(
    "validação para cpf_cnpj (CNPJ)",
    "/api/v1/validate",
    "POST",
    data={
        "type": "cpf_cnpj",
        "data": unique_cnpj,
        "client_identifier": unique_client_id_cnpj,
        "operator_identifier": "teste_automatizado_cnpj"
    }
)

# --- Testando validação para email ---
# Gerar um email único por execução
unique_email = f"test.{uuid.uuid4().hex[:8]}@example.com"
unique_client_id_email = f"cliente_email_{uuid.uuid4().hex[:8]}"
run_test(
    "validação para email",
    "/api/v1/validate",
    "POST",
    data={
        "type": "email",
        "data": unique_email,
        "client_identifier": unique_client_id_email,
        "operator_identifier": "teste_automatizado_email"
    }
)

# --- Testando validação para endereco ---
# Gerar um endereço único por execução (variando o número e complemento)
unique_address_number = random.randint(1, 9999)
unique_address_complement = f"apto {random.randint(1, 999)}"
unique_client_id_address = f"cliente_endereco_{uuid.uuid4().hex[:8]}"
run_test(
    "validação para endereco",
    "/api/v1/validate",
    "POST",
    data={
        "type": "endereco",
        "data": {
            "cep": "01001000",
            "logradouro": "Praça da Sé",
            "numero": str(unique_address_number),
            "bairro": "Sé",
            "cidade": "São Paulo",
            "estado": "SP",
            "complemento": unique_address_complement
        },
        "client_identifier": unique_client_id_address,
        "operator_identifier": "teste_automatizado_endereco"
    }
)

# --- Testando a eleição de Golden Record para um email ---
print("\n--- Testando eleição de Golden Record para Email ---")
# **CORREÇÃO AQUI**: Usar um domínio de email que realmente aceita emails para testar a lógica do Golden Record
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
    print("Teste GR 1 (Inicial): FAILED - Primeiro registro NÃO se tornou o GR.")


# Segundo registro (deve tentar se tornar o GR, se a pontuação for maior ou igual e for mais recente)
# O dado_normalizado deve ser o mesmo para o GR funcionar.
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
# Verifique se o segundo registro é o GR ou se o GR ainda aponta para o primeiro (depende da lógica de score)
if second_gr_is_golden and second_gr_golden_id == second_gr_id:
    print("Teste GR 2 (Atualização): PASSED - Segundo registro se tornou o GR.")
elif not second_gr_is_golden and second_gr_golden_id == initial_gr_id:
    print("Teste GR 2 (Atualização): PASSED - Segundo registro não se tornou GR, mas GR ainda aponta para o primeiro. (Comportamento esperado se o score não for superior).")
else:
    print("Teste GR 2 (Atualização): FAILED - GR não se comportou como esperado.")


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
            if record.get("is_golden_record") or record.get("golden_record_id_for_normalized_data") in [str(initial_gr_id), str(second_gr_id)]:
                print(f"Found Golden Record related record for {gr_email_data}: ID {record.get('record_id')}, is_golden_record={record.get('is_golden_record')}, golden_record_id_for_normalized_data={record.get('golden_record_id_for_normalized_data')}")
                found_gr_in_history = True
else:
    print(f"Erro ao obter histórico para GR: {history_response_gr.get('message', 'Nenhuma mensagem de erro.')}")


if found_gr_in_history:
    print("Teste GR 3 (Histórico): PASSED - Registro relacionado ao Golden Record para 'golden.record.test.valid@gmail.com' encontrado no histórico.")
else:
    print("Teste GR 3 (Histórico): FAILED - Registro relacionado ao Golden Record para 'golden.record.test.valid@gmail.com' não encontrado no histórico.")

# --- Teste de Qualificação e Enriquecimento Simulados ---
print("\n--- Teste de Qualificação e Enriquecimento Simulados (Email) ---")
# Este teste agora reflete a lógica adicionada em ValidationService._perform_enrichment_and_qualification
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


# --- Testando histórico (limite=5, deletados=False) ---
# Esta requisição não insere dados, então não precisa de unique_id
run_test(
    "histórico (limite=5, deletados=False)",
    "/api/v1/history", # Remove parâmetros da URL, passe via `params`
    "GET",
    params={"limit": 5, "include_deleted": False}
)

print("\nTodos os testes concluídos.")
