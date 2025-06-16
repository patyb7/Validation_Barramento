# app/database/manager.py

import asyncpg
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance: Optional['DatabaseManager'] = None
    _connection_pool: Optional[asyncpg.pool.Pool] = None
    _db_url: Optional[str] = None

    def __new__(cls): # <--- Remova o db_url do __new__
        """
        Garanto que apenas uma instância de DatabaseManager seja criada (Singleton).
        O db_url será setado via o método connect ou get_instance.
        """
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            # Não inicialize _db_url nem _connection_pool aqui
            cls._instance._db_url = None 
            cls._instance._connection_pool = None
            logger.info("DatabaseManager: Primeira instância singleton criada.")
        return cls._instance

    def __init__(self, db_url: Optional[str] = None):
        # Este __init__ só é chamado na primeira vez.
        # Se db_url for passado, use-o para setar o _db_url da instância.
        if self._db_url is None and db_url is not None:
             self._db_url = db_url

    @classmethod
    def get_instance(cls, db_url: Optional[str] = None) -> 'DatabaseManager':
        """
        Retorna a instância única do DatabaseManager.
        Se for a primeira vez e db_url for fornecido, inicializa-o.
        """
        if cls._instance is None:
            if db_url is None:
                raise ValueError("db_url deve ser fornecido na primeira chamada de get_instance.")
            # Chama __new__ e __init__ para a primeira instância
            instance = cls() 
            instance._db_url = db_url # Define o db_url da instância
            logger.info(f"DatabaseManager: Primeira instância configurada com URL.")
            return instance
        else:
            # Se a instância já existe e uma nova URL foi passada (e é diferente), avise.
            if db_url is not None and cls._instance._db_url != db_url:
                logger.warning(f"DatabaseManager: Tentativa de reconfigurar URL para singleton existente. Usando a URL original.")
            return cls._instance

    # Adicione esta propriedade para acessar o pool
    @property
    def pool(self) -> asyncpg.pool.Pool:
        """Propriedade para acessar o pool de conexões. Garante que o pool foi inicializado."""
        if self._connection_pool is None: # Use _connection_pool aqui
            raise RuntimeError("Pool de conexões não inicializado. Chame 'connect()' primeiro.")
        return self._connection_pool

    async def connect(self):
        """
        Cria o pool de conexões assíncrono. Deve ser chamado no startup da aplicação.
        """
        if self._connection_pool is None: # Use _connection_pool aqui
            if not self._db_url: # Use _db_url da instância
                raise RuntimeError("DATABASE_URL não configurada no DatabaseManager antes de tentar conectar. Chame DatabaseManager(db_url) ou get_instance(db_url) primeiro.")
            try:
                logger.info("DatabaseManager: Criando pool de conexões asyncpg...")
                self._connection_pool = await asyncpg.create_pool( # Use _connection_pool aqui
                    dsn=self._db_url, # Use _db_url da instância
                    min_size=1, 
                    max_size=10,
                    timeout=60,
                )
                logger.info("DatabaseManager: Pool de conexões asyncpg criado com sucesso.")
            except Exception as e:
                logger.critical(f"DatabaseManager: Falha CRÍTICA ao criar pool de conexões: {e}", exc_info=True)
                raise # Re-lança a exceção para que a aplicação não inicie

    async def get_connection(self):
        """Obtém uma conexão do pool."""
        return await self.pool.acquire() # Usa a propriedade pool

    async def put_connection(self, conn):
        """Libera uma conexão de volta para o pool."""
        if self._connection_pool is not None and conn is not None: # Use _connection_pool aqui
            await self._connection_pool.release(conn)

    async def close_pool(self):
        """Fecha o pool de conexões."""
        if self._connection_pool: # Use _connection_pool aqui
            logger.info("DatabaseManager: Fechando pool de conexões...")
            await self._connection_pool.close()
            self._connection_pool = None # Use _connection_pool aqui
            self._instance = None # Resetar a instância
            logger.info("DatabaseManager: Pool de conexões fechado.")