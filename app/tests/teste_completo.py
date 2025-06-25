import requests
import json
import logging
import time
import uuid
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurações da API
BASE_URL = "http://127.0.0.1:8001/api/v1" # Certifique-se de que este é o prefixo correto da sua API

# === CHAVES DE API REAIS DO SEU api_keys.json ===
# Certifique-se de que estas chaves realmente existem e têm as permissões esperadas no seu api_keys.json
VALID_API_KEY_ANALYTICS = "API_KEY_ANALYTICS_READ_ONLY" # Ex: tem apenas permissão de leitura para /history
API_KEY_FULL_PERMISSIONS = "API_KEY_PSDC" # Ex: tem can_delete_records: true, can_check_duplicates: true, etc.
API_KEY_NO_PERMISSIONS = "API_KEY_TESTING" # Ex: tem can_delete_records: false, can_check_duplicates: false, etc.
INVALID_API_KEY = "INVALID_KEY_XYZ" # Chave que NÃO existe no seu api_keys.json

# Variáveis para armazenar resultados dos testes
test_results = {}
record_id_for_manipulation = None

def generate_unique_id(prefix: str = "") -> str:
    """Gera um ID único baseado em UUID para evitar colisões em client_identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def run_test(name, url, method="GET", headers=None, payload=None, params=None, expected_status=200, api_key=None, print_payload=True):
    """
    Executa um único teste de API e imprime o resultado.
    Armazena o resultado no dicionário global `test_results`.
    """
    logger.info(f"\n--- Testando: {name} ---")
    
    request_headers = {}
    # Adiciona Content-Type para requisições com payload
    if payload:
        request_headers["Content-Type"] = "application/json"
    
    if headers:
        request_headers.update(headers)
    
    if api_key:
        request_headers["X-API-Key"] = api_key
    elif "X-API-Key" in request_headers:
        # Garante que a API Key não está no cabeçalho se não for fornecida explicitamente para o teste
        del request_headers["X-API-Key"]

    try:
        response = None
        if method == "GET":
            response = requests.get(url, headers=request_headers, params=params, timeout=10)
        elif method == "POST":
            response = requests.post(url, headers=request_headers, json=payload, params=params, timeout=10)
        elif method == "DELETE":
            response = requests.delete(url, headers=request_headers, params=params, timeout=10)
        elif method == "PUT":
            response = requests.put(url, headers=request_headers, json=payload, params=params, timeout=10)
        else:
            logger.error(f"ERRO: Método HTTP '{method}' não suportado na função run_test.")
            test_results[name] = False
            return {"detail": "Método HTTP não suportado."}

        status_code = response.status_code
        response_json = {}
        try:
            response_json = response.json()
        except json.JSONDecodeError:
            logger.warning(f"Resposta não é um JSON válido. Status: {status_code}, Conteúdo: {response.text}")
            # Se não é JSON, use o texto da resposta para depuração
            response_json = {"raw_response": response.text}

        logger.info(f"URL: {url}")
        logger.info(f"Método: {method}")
        logger.info(f"Headers: {request_headers}")
        if print_payload and payload:
            logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        else:
            logger.info("Payload: N/A (ou oculto)")
        logger.info(f"Parâmetros: {params if params else 'N/A'}")
        logger.info(f"Status Code: {status_code} (Esperado: {expected_status})")
        logger.info(f"Response Body: {json.dumps(response_json, indent=2)}")

        if status_code == expected_status:
            logger.info(f"SUCESSO: Status code {status_code} é o esperado.")
            test_results[name] = True
            return response_json
        else:
            logger.error(f"FALHA: Status code inesperado. Esperado {expected_status}, Recebido {status_code}")
            test_results[name] = False
            return response_json

    except requests.exceptions.Timeout:
        logger.error(f"ERRO: Requisição para {url} excedeu o tempo limite (10s).")
        test_results[name] = False
        return {"detail": "Timeout de requisição."}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"ERRO: Falha de conexão para {url}: {e}. Certifique-se de que a API está rodando e acessível.")
        test_results[name] = False
        return {"detail": f"Erro de conexão: {e}"}
    except Exception as e:
        logger.error(f"ERRO: Erro inesperado durante o teste '{name}': {e}", exc_info=True)
        test_results[name] = False
        return {"detail": f"Erro inesperado: {e}"}
    finally:
        logger.info("-" * 40)

logger.info("Iniciando execução dos testes da API do Barramento de Validação...")

# --- Testes de Health Check ---
# Teste de health check sem API Key (espera-se 401 se a autenticação for global)
run_test(
    "Health Check (API Key Ausente - Esperado 401)",
    f"{BASE_URL}/health",
    expected_status=401 # Agora espera 401, pois a chave está ausente
)

# Testes de Autenticação
run_test(
    "Autenticação: API Key Ausente (Validate Endpoint)",
    f"{BASE_URL}/validate",
    method="POST",
    payload={"type": "telefone", "data": "123"},
    expected_status=401,
    print_payload=False
)

run_test(
    "Autenticação: API Key Inválida (Validate Endpoint)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=INVALID_API_KEY,
    payload={"type": "telefone", "data": "123"},
    expected_status=401,
    print_payload=False
)

run_test(
    "Autenticação: API Key Válida (API_KEY_ANALYTICS - Health Endpoint)",
    f"{BASE_URL}/health",
    api_key=VALID_API_KEY_ANALYTICS,
    expected_status=200
)

# --- Testes de Validação ---
# Telefone Válido
run_test(
    "Validação Telefone BR (Válido)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "telefone",
        "data": "+5511999998888",
        "client_identifier": generate_unique_id("tel_val_br"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=200
)

# Telefone Sequencial/Repetido (esperado inválido)
run_test(
    "Validação Telefone (Sequencial/Repetido)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "telefone",
        "data": "+5511912345678", # Exemplo de número sequencial (pode ser "111111111" ou "123456789")
        "client_identifier": generate_unique_id("tel_inv_seq"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=400 # Se a sua regra identifica isso como inválido
)

# CPF Válido
run_test(
    "Validação CPF (Válido)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "cpf_cnpj",
        "data": "12345678901", # Este CPF é matematicamente válido, ajuste se sua regra blacklista
        "client_identifier": generate_unique_id("cpf_val"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=200
)

# CPF Inválido
run_test(
    "Validação CPF (Inválido)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "cpf_cnpj",
        "data": "11122233344", # Exemplo de CPF inválido
        "client_identifier": generate_unique_id("cpf_inv"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=400
)

# CNPJ Válido
run_test(
    "Validação CNPJ (Válido)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "cpf_cnpj",
        "data": "12345678000195", # Exemplo de CNPJ válido
        "client_identifier": generate_unique_id("cnpj_val"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=200
)

# CNPJ Inválido
run_test(
    "Validação CNPJ (Inválido)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "cpf_cnpj",
        "data": "12345678000190", # Exemplo de CNPJ inválido
        "client_identifier": generate_unique_id("cnpj_inv"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=400
)

# Email Válido
run_test(
    "Validação Email (Válido)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "email",
        "data": f"teste.{generate_unique_id()}@example.com",
        "client_identifier": generate_unique_id("email_val"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=200
)

# Email Sintaxe Inválida
run_test(
    "Validação Email (Sintaxe Inválida)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "email",
        "data": "usuario@dominio", # Email com sintaxe inválida
        "client_identifier": generate_unique_id("email_inv_syntax"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=400
)

# Endereço Válido
run_test(
    "Validação Endereço (Válido)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "endereco",
        "data": {
            "cep": "01001000",
            "logradouro": "Praça da Sé",
            "numero": str(random.randint(1, 9999)),
            "bairro": "Sé",
            "cidade": "São Paulo",
            "estado": "SP"
        },
        "client_identifier": generate_unique_id("end_val"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=200
)

# Endereço CEP Inválido
run_test(
    "Validação Endereço (CEP Inválido)",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "endereco",
        "data": {
            "cep": "0000000", # CEP com formato inválido
            "logradouro": "Rua Teste",
            "numero": "123",
            "cidade": "Cidade",
            "estado": "UF"
        },
        "client_identifier": generate_unique_id("end_inv_cep"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=400 # ou 422, dependendo de como sua validação lida com isso
)

# Tipo Não Implementado
run_test(
    "Validação Tipo Não Implementado",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "dados_bancarios", # Tipo de validação não esperado
        "data": "123456",
        "client_identifier": generate_unique_id("unimplemented"),
        "operator_identifier": "teste_automatizado"
    },
    expected_status=400 # O erro original esperava 501, mas 400 é mais apropriado para "não suportado"
)

# --- Testes de Histórico (Criação de Registros para popular) ---
response_hist1 = run_test(
    "Criar Registro para Histórico 1",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "telefone",
        "data": "+5511911111111",
        "client_identifier": generate_unique_id("hist_1")
    },
    expected_status=200
)

response_hist2 = run_test(
    "Criar Registro para Histórico 2",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=VALID_API_KEY_ANALYTICS,
    payload={
        "type": "email",
        "data": f"hist.{generate_unique_id()}@teste.com",
        "client_identifier": generate_unique_id("hist_2")
    },
    expected_status=200
)

# Aguarda um pouco para os registros serem processados (útil se houver processamento em background)
time.sleep(1)

# Teste de Histórico (busca)
run_test(
    "Histórico (Padrão: 5 registros, não deletados)",
    f"{BASE_URL}/history",
    api_key=VALID_API_KEY_ANALYTICS,
    params={"limit": 5, "include_deleted": False},
    expected_status=200
)

# --- Testes de Manipulação de Registros (GET, SOFT-DELETE, RESTORE, REPROCESS) ---
# Primeiro, crie um registro que possa ser manipulado
create_manipulate_record_response = run_test(
    "Criar Registro para Manipulação",
    f"{BASE_URL}/validate",
    method="POST",
    api_key=API_KEY_FULL_PERMISSIONS, # Use uma chave com permissão completa
    payload={
        "type": "email",
        "data": f"manipulate.{generate_unique_id()}@teste.com",
        "client_identifier": generate_unique_id("manipulate"),
        "operator_identifier": "teste_manipulacao"
    },
    expected_status=200
)

# AQUI ESTÁ A CORREÇÃO MAIS IMPORTANTE:
if create_manipulate_record_response and \
   create_manipulate_record_response.get("status") == "success" and \
   create_manipulate_record_response.get("data") and \
   create_manipulate_record_response["data"].get("id_registro"):
    
    record_id_for_manipulation = create_manipulate_record_response["data"]["id_registro"]
    logger.info(f"ID do registro para manipulação obtido: {record_id_for_manipulation}")

    # Obter Detalhes de Registro Existente
    run_test(
        f"Obter Detalhes de Registro Existente ({record_id_for_manipulation})",
        f"{BASE_URL}/records/{record_id_for_manipulation}",
        api_key=API_KEY_FULL_PERMISSIONS,
        expected_status=200
    )

    # Soft-delete de Registro Existente
    run_test(
        f"Soft-delete Registro Existente ({record_id_for_manipulation})",
        f"{BASE_URL}/records/{record_id_for_manipulation}/soft-delete",
        method="PUT",
        api_key=API_KEY_FULL_PERMISSIONS,
        expected_status=200
    )

    # Tentar Obter Detalhes de Registro Deletado (espera-se 404 se a API ocultar deletados por padrão)
    # ou 200 se a API retornar com 'deleted_at' preenchido
    run_test(
        f"Obter Detalhes de Registro Deletado ({record_id_for_manipulation})",
        f"{BASE_URL}/records/{record_id_for_manipulation}",
        api_key=API_KEY_FULL_PERMISSIONS,
        expected_status=404 # Ajuste para 200 se a sua API retorna registros deletados mas com flag
    )
    
    # Restaurar Registro Deletado
    run_test(
        f"Restaurar Registro Deletado ({record_id_for_manipulation})",
        f"{BASE_URL}/records/{record_id_for_manipulation}/restore",
        method="PUT",
        api_key=API_KEY_FULL_PERMISSIONS,
        expected_status=200
    )

    # Obter Detalhes de Registro Restaurado (deve voltar a ser 200)
    run_test(
        f"Obter Detalhes de Registro Restaurado ({record_id_for_manipulation})",
        f"{BASE_URL}/records/{record_id_for_manipulation}",
        api_key=API_KEY_FULL_PERMISSIONS,
        expected_status=200
    )

    # Reprocessar Registro
    run_test(
        f"Reprocessar Registro Existente ({record_id_for_manipulation})",
        f"{BASE_URL}/records/{record_id_for_manipulation}/reprocess",
        method="PUT",
        api_key=API_KEY_FULL_PERMISSIONS,
        expected_status=200
    )

else:
    logger.error("Não foi possível obter um ID de registro para realizar testes de manipulação. Verifique a estrutura da resposta da API.")
    logger.error(f"Resposta de criação recebida: {json.dumps(create_manipulate_record_response, indent=2)}")


# Testes de registros inexistentes e permissões negadas (sempre executados)
non_existent_id = str(uuid.uuid4()) # Gerar um novo ID inexistente para cada execução
run_test(
    f"Obter Detalhes de Registro Inexistente ({non_existent_id})",
    f"{BASE_URL}/records/{non_existent_id}",
    api_key=API_KEY_FULL_PERMISSIONS,
    expected_status=404
)

run_test(
    f"Soft-delete Registro Inexistente ({non_existent_id})",
    f"{BASE_URL}/records/{non_existent_id}/soft-delete",
    method="PUT",
    api_key=API_KEY_FULL_PERMISSIONS,
    expected_status=404
)

run_test(
    f"Restaurar Registro Inexistente ({non_existent_id})",
    f"{BASE_URL}/records/{non_existent_id}/restore",
    method="PUT",
    api_key=API_KEY_FULL_PERMISSIONS,
    expected_status=404
)

run_test(
    f"Reprocessar Registro Inexistente ({non_existent_id})",
    f"{BASE_URL}/records/{non_existent_id}/reprocess",
    method="PUT",
    api_key=API_KEY_FULL_PERMISSIONS,
    expected_status=404
)

# Testes de permissão negada para operações de manipulação
# Usar um ID de registro EXISTENTE para estes testes de permissão para isolar o erro de permissão.
# Se o record_id_for_manipulation não foi obtido, o teste usará um ID inexistente,
# o que ainda resultará em 403 (perm_negada) se a rota for acessada antes de verificar o ID.
test_id_for_perms = record_id_for_manipulation if record_id_for_manipulation else str(uuid.uuid4())

run_test(
    f"Soft-delete (Permissão Negada) - ID: {test_id_for_perms}",
    f"{BASE_URL}/records/{test_id_for_perms}/soft-delete",
    method="PUT",
    api_key=API_KEY_NO_PERMISSIONS,
    expected_status=403
)

run_test(
    f"Restaurar (Permissão Negada) - ID: {test_id_for_perms}",
    f"{BASE_URL}/records/{test_id_for_perms}/restore",
    method="PUT",
    api_key=API_KEY_NO_PERMISSIONS,
    expected_status=403
)

run_test(
    f"Reprocessar (Permissão Negada) - ID: {test_id_for_perms}",
    f"{BASE_URL}/records/{test_id_for_perms}/reprocess",
    method="PUT",
    api_key=API_KEY_NO_PERMISSIONS,
    expected_status=403
)

logger.info("\nTodos os testes da API concluídos.")

# --- Sumário dos Resultados ---
total_tests = len(test_results)
passed_tests = sum(1 for result in test_results.values() if result)
failed_tests = total_tests - passed_tests

print("\n" + "="*50)
print("             SUMÁRIO DOS RESULTADOS DOS TESTES")
print("="*50)
for name, result in test_results.items():
    status = "SUCESSO" if result else "FALHA"
    print(f"- {name}: {status}")

print("\n" + "="*50)
print(f"Total de Testes Executados: {total_tests}")
print(f"Testes Passados:          {passed_tests}")
print(f"Testes Falhos:            {failed_tests}")
print("="*50)

if failed_tests > 0:
    logger.error("ATENÇÃO: Existem testes falhos. Verifique os logs acima para detalhes.")
else:
    logger.info("TODOS OS TESTES PASSARAM COM SUCESSO! A API está funcionando conforme o esperado.")