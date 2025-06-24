# app/api/routers/__init__.py

import logging
from app.config.settings import settings # Importa o objeto settings

logger = logging.getLogger(__name__)

# Se este arquivo __init__.py precisa fazer algo com as API keys
# Por exemplo, inicializar algo que usa api_keys
try:
    # Acessando API_KEYS através do objeto settings
    # Esta linha foi ajustada para usar settings.API_KEYS
    logger.info(f"Router __init__.py: API Keys carregadas com sucesso: {len(settings.API_KEYS)} chaves.")
except Exception as e:
    logger.error(f"Erro ao carregar API Keys em routers/__init__.py: {e}")
    # Dependendo da necessidade, você pode querer levantar a exceção ou apenas logar
    # raise e # Descomente se um erro aqui deve impedir a inicialização
# --- Importar os APIRouter de cada arquivo de rota ---