import os
import sys
import locale
from dotenv import load_dotenv

print(f"Current Working Directory: {os.getcwd()}")
dotenv_path = os.path.join(os.getcwd(), '.env')
print(f"Caminho do .env que será carregado: {dotenv_path}")

# Tenta carregar o .env explicitamente do diretório atual
# verbose=True vai mostrar se o arquivo foi carregado
# override=True vai garantir que ele sobrescreva variáveis existentes
load_dotenv(dotenv_path=dotenv_path, verbose=True, override=True)

db_password_os_env = os.getenv("DB_PASSWORD")

print(f"\n--- Resultado da leitura ---")
print(f"DB_PASSWORD lido com os.getenv: '{db_password_os_env}'")
if db_password_os_env:
    try:
        print(f"DB_PASSWORD em HEX (UTF-8): {db_password_os_env.encode('utf-8').hex()}")
    except UnicodeEncodeError as uee:
        print(f"Erro ao codificar DB_PASSWORD para UTF-8: {uee}")
else:
    print("DB_PASSWORD não encontrado ou é None.")

print(f"\n--- Detalhes do Ambiente Python ---")
print(f"PYTHONIOENCODING: {os.getenv('PYTHONIOENCODING')}")
print(f"PYTHONUTF8: {os.getenv('PYTHONUTF8')}")
print(f"SYS.GETDEFAULTENCODING: {sys.getdefaultencoding()}")
print(f"Locale preferred encoding: {locale.getpreferredencoding()}")