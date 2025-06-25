# app/tests/test_api.py
import requests
import json
import uuid # Para gerar IDs únicos
import random # Para gerar números aleatórios para dados de teste
import time # Para adicionar um pequeno delay se necessário

# Base URL da sua API
BASE_URL = "http://127.0.0.1:8001"
# Use a sua API Key real aqui. Certifique-se de que ela está ativa no api_keys.json
# Exemplo: "API_KEY_PSDC" se essa for a string literal da sua chave
API_KEY_PSDC = "API_KEY_PSDC" # Substitua pela sua API Key do sistema PSDC

headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY_PSDC
}

def run_test(test_name, endpoint, method, data=None, params=None):
    print(f"\n--- Testando {test_name} ---")
    response = requests.request(method, f"{BASE_URL}{endpoint}", headers=headers, json=data, params=params)
    print(f"Status Code: {response.status_code}")
    # Usa ensure_ascii=False para exibir caracteres especiais corretamente
    print(f"Response JSON: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print("----------------------------------------")
    return response.json() # Retorna a resposta JSON para verificações

print("Iniciando execução dos testes da API...")

# --- Testando validação para telefone ---
# Gerar um dado de telefone único por execução
unique_phone_number = f"+55119{random.randint(10000000, 99999999)}"
unique_client_id_phone = f"cliente_phone_{uuid.uuid4().hex[:8]}"
run_test(
    "validação para telefone",
    "/api/v1/validate",
    "POST",
    data={
        "type": "telefone",
        "data": unique_phone_number,
        "client_identifier": unique_client_id_phone,
        "operator_identifier": "teste_automatizado"
    }
)

# --- Testando validação para cpf_cnpj (CPF inválido, para RN_TEL_INVALID_APP) ---
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

# --- Testando validação para cpf_cnpj (CNPJ inválido, para RN_TEL_INVALID_APP) ---
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
# Usaremos um dado normalizado fixo para testar o GR, mas client_identifier único
gr_email_data = "golden.record.test@example.com"

# Primeiro registro (deve se tornar o GR inicial)
initial_gr_client_id = f"gr_client_1_{uuid.uuid4().hex[:8]}"
print("\n--- Inserindo o primeiro registro para Golden Record ---")
response_1 = run_test(
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

initial_gr_id = response_1.get("record_id")
initial_gr_is_golden = response_1.get("is_golden_record_for_this_transaction")
initial_gr_golden_id = response_1.get("golden_record_id_for_normalized_data")

print(f"Status do 1º registro: is_golden_record_for_this_transaction={initial_gr_is_golden}, golden_record_id_for_normalized_data={initial_gr_golden_id}")
if initial_gr_is_golden and initial_gr_golden_id == initial_gr_id:
    print("Teste GR 1 (Inicial): PASSED - Primeiro registro se tornou o GR.")
else:
    print("Teste GR 1 (Inicial): FAILED - Primeiro registro NÃO se tornou o GR.")


# Segundo registro (deve tentar se tornar o GR, se a pontuação for maior ou igual e for mais recente)
# Para fins de teste, vamos assumir que o segundo registro, por ser mais recente,
# ou por possuir um "score" implicitamente maior (se houver essa lógica),
# ou simplesmente por ser uma nova inserção, pode se tornar o GR.
# O dado_normalizado deve ser o mesmo para o GR funcionar.
time.sleep(1) # Pequeno delay para garantir que created_at seja diferente

second_gr_client_id = f"gr_client_2_{uuid.uuid4().hex[:8]}"
print("\n--- Inserindo o segundo registro para Golden Record ---")
response_2 = run_test(
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

second_gr_id = response_2.get("record_id")
second_gr_is_golden = response_2.get("is_golden_record_for_this_transaction")
second_gr_golden_id = response_2.get("golden_record_id_for_normalized_data")

print(f"Status do 2º registro: is_golden_record_for_this_transaction={second_gr_is_golden}, golden_record_id_for_normalized_data={second_gr_golden_id}")
if second_gr_is_golden and second_gr_golden_id == second_gr_id:
    print("Teste GR 2 (Atualização): PASSED - Segundo registro se tornou o GR.")
else:
    print("Teste GR 2 (Atualização): FAILED - Segundo registro NÃO se tornou o GR. Isso pode ser esperado dependendo da lógica de eleição de GR.")


# --- Verificação final do Golden Record através do histórico ou busca específica ---
print("\n--- Verificando o Golden Record no histórico ---")
# Idealmente, você teria um endpoint para buscar por dado_normalizado
# Por agora, buscaremos o histórico e filtraremos
history_response = run_test(
    "Obter Histórico para GR",
    f"/api/v1/history",
    "GET",
    params={"limit": 10, "include_deleted": False}
)

found_gr = False
if history_response and history_response.get("status") == "success":
    for record in history_response.get("data", []):
        if record.get("dado_normalizado") == gr_email_data:
            if record.get("is_golden_record"):
                print(f"Found Golden Record for {gr_email_data}: ID {record.get('record_id')}")
                found_gr = True
            # Verifique se o golden_record_id_for_normalized_data aponta para o GR atual
            if record.get("golden_record_id_for_normalized_data") == second_gr_id:
                print(f"Record {record.get('record_id')} points to the correct Golden Record {second_gr_id}.")

if found_gr:
    print("Teste GR 3 (Histórico): PASSED - Golden Record encontrado no histórico.")
else:
    print("Teste GR 3 (Histórico): FAILED - Golden Record para 'golden.record.test@example.com' não encontrado no histórico.")

# --- Testando histórico (limite=5, deletados=False) ---
# Esta requisição não insere dados, então não precisa de unique_id
run_test(
    "histórico (limite=5, deletados=False)",
    "/api/v1/history", # Remove parâmetros da URL, passe via `params`
    "GET",
    params={"limit": 5, "include_deleted": False}
)

print("\nTodos os testes concluídos.")
