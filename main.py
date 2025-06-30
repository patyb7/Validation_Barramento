# G:/Projeto_Validador_Barramento/Validation_Barramento/main.py
import uvicorn
import logging
from app.api.api_main import app
import sys
import os
import fastapi

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    logger.info(f"Adicionado '{project_root}' ao sys.path para imports.")

if __name__ == "__main__":
    logger.info(f"Iniciando o servidor FastAPI...")
    logger.info(f"Acesse a API em: http://127.0.0.1:8000")
    logger.info(f"Documentação da API (Swagger UI): http://127.0.0.1:8000/docs")
    logger.info(f"APERTAR CTRL+C PARA SAIR DO SERVIÇO...")

    # O Uvicorn agora importará "app.api.api_main" porque 'app' está
    # no sys.path (devido à linha `sys.path.insert(0, project_root)` acima)
    uvicorn.run("app.api.api_main:app", host="0.0.0.0", port=8000, reload=True)