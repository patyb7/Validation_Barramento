# conftest.py (ou um arquivo de fixtures)
import pytest
import subprocess
import time
import requests

# Ajuste para o comando que inicia sua API
# Exemplo para FastAPI (se 'main.py' contém a instância 'app'):
# API_COMMAND = ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "5000"]
# Exemplo para Flask (se 'app.py' contém a instância 'app' e você usa gunicorn):
API_COMMAND = ["gunicorn", "app:app", "-b", "127.0.0.1:8001"]

API_BASE_URL = "http://127.0.0.1:5000/api"

@pytest.fixture(scope="session")
def live_api():
    """Fixture para iniciar e parar a API para os testes de integração."""
    print("\nIniciando a API para testes...")
    process = None
    try:
        # Inicia a API como um subprocesso.
        # Use o shell=True no Windows se os comandos não forem encontrados diretamente
        # ou use o caminho completo para python.exe no seu venv.
        process = subprocess.Popen(API_COMMAND, shell=True if platform.system() == "Windows" else False)
        
        # Espera um pouco para a API inicializar
        time.sleep(5) 
        
        # Opcional: Tenta conectar para garantir que a API está de pé
        retries = 5
        for i in range(retries):
            try:
                requests.get(f"{API_BASE_URL}/health") # Ou um endpoint de saúde que exista
                print("API iniciada e acessível.")
                break
            except requests.exceptions.ConnectionError:
                print(f"Tentando conectar à API... ({i+1}/{retries})")
                time.sleep(2)
        else:
            raise Exception("Não foi possível conectar à API após várias tentativas.")

        yield API_BASE_URL # Fornece a URL base da API para os testes

    finally:
        if process:
            print("Encerrando a API...")
            process.terminate() # Encerra o processo da API
            process.wait() # Espera o processo terminar
            print("API encerrada.")

# No seu test_tel_api.py, você passaria 'live_api' para suas funções de teste:
# def test_validate_phone_non_json_request(live_api):
#     endpoint = f"{live_api}/validate/phone"
#     # ... o restante do seu teste