import asyncpg
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance: Optional['DatabaseManager'] = None
    _pool: Optional[asyncpg.Pool] = None
    _database_url: Optional[str] = None
    _is_connected: bool = False

    # Remova o 'database_url' do __new__ para evitar que a primeira chamada "sem argumento" do singleton defina a URL.
    # Agora o __new__ apenas garante que uma instância exista.
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            logger.info("DatabaseManager: Primeira instância singleton criada.")
        return cls._instance

    # O método 'initialize' é chamado APENAS UMA VEZ para configurar o pool.
    # Ele verifica se já está conectado para evitar reconexões desnecessárias.
    async def initialize(self, database_url: str):
        if self._is_connected and self._pool is not None and self._database_url == database_url:
            logger.info("DatabaseManager: Pool de conexões já está conectado com a mesma URL.")
            return

        if self._pool is not None:
            logger.warning("DatabaseManager: Fechando pool de conexões existente antes de re-inicializar.")
            await self.close_pool()

        self._database_url = database_url
        try:
            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=1,  # Defina estes valores com base nas suas settings, se desejar
                max_size=10,
                timeout=60
            )
            self._is_connected = True
            logger.info(f"DatabaseManager: Pool de conexões asyncpg criado com sucesso para {self._database_url}.")
        except Exception as e:
            self._is_connected = False
            logger.critical(f"DatabaseManager: Falha ao criar pool de conexões para {self._database_url}: {e}", exc_info=True)
            raise

    # Remova o método connect() antigo ou adapte-o para chamar initialize()
    # Aqui, vamos substituir o connect() por initialize no startup event.

    async def get_connection(self) -> asyncpg.Connection:
        if not self._is_connected or self._pool is None:
            logger.error("DatabaseManager: Tentativa de obter conexão de um pool não inicializado ou desconectado.")
            raise Exception("Pool de conexões do banco de dados não está inicializado.")
        return await self._pool.acquire()

    async def put_connection(self, conn: asyncpg.Connection):
        if self._pool is not None:
            await self._pool.release(conn)

    async def close_pool(self):
        if self._pool:
            logger.info("DatabaseManager: Fechando pool de conexões...")
            await self._pool.close()
            self._pool = None
            self._is_connected = False
            logger.info("DatabaseManager: Pool de conexões fechado.")

    # Novo método estático para obter a instância, sem forçar a inicialização aqui.
    @classmethod
    def get_instance(cls) -> 'DatabaseManager':
        return cls.__new__(cls)
    