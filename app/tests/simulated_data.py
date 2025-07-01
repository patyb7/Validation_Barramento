# app/tests/simulated_data.py

# --- Bases de dados simuladas para CEP ---
SIMULATED_CEP_RESPONSES = {
    "01001000": { # Praça da Sé, SP (Válido, completo)
        "cep": "01001-000", "logradouro": "Praça da Sé", "complemento": "lado ímpar",
        "bairro": "Sé", "localidade": "São Paulo", "uf": "SP", "ibge": "3550308",
        "gia": "1004", "ddd": "11", "siafi": "7107"
    },
    "20040003": { # Rua da Quitanda, RJ (Válido, completo)
        "cep": "20040-003", "logradouro": "Rua da Quitanda", "complemento": "",
        "bairro": "Centro", "localidade": "Rio de Janeiro", "uf": "RJ", "ibge": "3304557",
        "gia": "", "ddd": "21", "siafi": "6001"
    },
    "70000001": { # Exemplo de CEP em Brasília
        "cep": "70000-001", "logradouro": "Esplanada dos Ministérios", "complemento": "",
        "bairro": "Zona Cívico-Administrativa", "localidade": "Brasília", "uf": "DF",
        "ibge": "5300108", "gia": "", "ddd": "61", "siafi": "7000"
    },
    "99999999": {"erro": True}, # CEP não encontrado pela API
    "12345678": {"erro": True}, # Outro CEP não encontrado
    "88888888": {"erro": True}, # Sequencial, e também não encontrado na simulação
    "07273120": {"erro": True}, # CEP específico para teste de "não encontrado na base externa"
}

# --- Bases de dados simuladas para CPF e CNPJ ---
SIMULATED_CPF_DATABASE = {
    "31984625845": {"name": "Ana Paula Silva Souza", "status_receita_federal": "REGULAR", "is_active": True},
    "55566677788": {"name": "Cliente Exemplo CPF Irregular", "status_receita_federal": "SUSPENSO", "is_active": False},
    "00000000000": {"name": "CPF Sequencial Inválido", "status_receita_federal": None, "is_active": False},
    "33322211144": {"name": "João Válido Teste", "status_receita_federal": "REGULAR", "is_active": True},
}

SIMULATED_CNPJ_DATABASE = {
    "12345678000190": {"name": "Empresa Teste CNPJ Válido", "status_receita_federal": "ATIVA", "is_active": True},
    "98765432000121": {"name": "Empresa Teste CNPJ Baixada", "status_receita_federal": "BAIXADA", "is_active": False},
    "11111111111111": {"name": "CNPJ Sequencial Inválido", "status_receita_federal": None, "is_active": False},
}

# --- Base de dados simulada para RGs (apenas dígitos) ---
SIMULATED_RG_DATABASE = {
    "344882504": {"customer_name": "Ana Paula Silva Souza", "is_active": True},
    "123456789": {"customer_name": "João Teste", "is_active": True},
    "987654321": {"customer_name": "Maria Exemplo", "is_active": False}, # RG inativo
    "111111111": {"customer_name": "Valdemar Valido", "is_active": True}, # RG Válido para teste
}

# --- Base de dados simulada para Celulares (apenas dígitos, formato DDI+DDD+NUMERO) ---
SIMULATED_PHONE_DATABASE = {
    "5511983802243": {"customer_name": "Ana Paula Silva Souza", "is_active": True, "operator": "Claro"},
    "5521998765432": {"customer_name": "João Teste", "is_active": True, "operator": "Vivo"},
    "5561912345678": {"customer_name": "Maria Exemplo", "is_active": False, "operator": "Tim"}, # Celular inativo
    "5511911111111": {"customer_name": "Telma Telefonica", "is_active": True, "operator": "Oi"},
}

# --- Para validação de consistência de endereço (CEP vs. Logradouro/Bairro/Cidade/Estado) ---
# Usado pelo AddressValidator para verificar se o endereço fornecido *corresponde* ao que o CEP "deveria" retornar.
SIMULATED_ADDRESS_CONSISTENCY_MAP = {
    "01001000": { # Praça da Sé, SP
        "logradouro": "Praça da Sé", "bairro": "Sé", "localidade": "São Paulo", "uf": "SP"
    },
    "20040003": { # Rua da Quitanda, RJ
        "logradouro": "Rua da Quitanda", "bairro": "Centro", "localidade": "Rio de Janeiro", "uf": "RJ"
    },
    # Exemplo de CEP que terá inconsistência se os dados de entrada não corresponderem
    "99999999": { # Este CEP simula inconsistência grave
        "logradouro": "Rua Ficticia", "bairro": "Bairro Ficticio", "localidade": "Cidade Ficticia", "uf": "FI"
    }
}

# --- CEP específico para simular falha de API (erro de conexão/timeout) ---
SIMULATED_CEP_API_FAILURE_CEP = "99999000"