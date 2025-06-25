# app/api/routers/__init__.py

import logging
# from app.config.settings import settings # Não é mais necessário importar settings aqui para API Keys

logger = logging.getLogger(__name__)

# O código de carregamento de API Keys foi movido para o APIKeyManager e a inicialização no main.py.
# Este arquivo __init__.py deve ser usado principalmente para a organização de módulos de roteador.
# Removido o bloco try...except que tentava acessar settings.API_KEYS, pois não existe mais.

# --- Importar os APIRouter de cada arquivo de rota ---
# Estas linhas são críticas para que as rotas sejam reconhecidas pelo FastAPI.
# Elas não precisam de acesso direto às configurações globais de API Keys aqui.

# Não é necessário um log de "API Keys carregadas com sucesso" aqui, pois o APIKeyManager já o faz.
# Caso você precise de alguma lógica de inicialização de router que dependa das chaves,
# isso deve ser feito dentro da função lifespan no main.py ou via injeção de dependência nos endpoints,
# não neste __init__.py.