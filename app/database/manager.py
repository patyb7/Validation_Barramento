# app/database/manager.py
import asyncpg
import logging
from typing import Optional, ContextManager

# Configuração de logging específica para este módulo
# Isso permite um controle mais granular dos logs do DatabaseManager
logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Classe Singleton para gerenciar o pool de conexões com o banco de dados PostgreSQL.
    
    Esta implementação garante que:
    1. Apenas uma instância do gerenciador (e, portanto, apenas um pool de conexões asyncpg)
       exista durante todo o ciclo de vida da aplicação.
    2. O pool de conexões seja inicializado de forma segura e fechado corretamente.
    3. Forneça um método conveniente para adquirir conexões do pool.
    4. Seja thread-safe (devido à natureza do singleton e operações assíncronas).
    """
    # Atributos de classe para o padrão Singleton e o pool de conexões
    _instance: Optional["DatabaseManager"] = None
    _pool: Optional[asyncpg.Pool] = None
    _db_url: Optional[str] = None
    # Atributo de classe para o logger, garantindo que ele esteja sempre disponível
    # antes que qualquer método da instância tente acessá-lo.
    # Usamos o logger definido acima para este módulo.
    logger: logging.Logger = logger
    # O método __new__ é chamado antes do __init__ para controlar a criação da instância.
    def __new__(cls, *args, **kwargs) -> "DatabaseManager":
        """
        Controla a criação da instância para garantir que apenas uma seja criada.
        """
        if cls._instance is None:
            cls.logger.info("DatabaseManager: Detectando a primeira requisição. Criando instância singleton.")
            # Chama o __new__ da classe pai para criar a instância real
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            # Sinaliza que esta é a primeira inicialização para evitar re-inicializações
            # de atributos que só devem ocorrer uma vez.
            cls._instance._initialized = False 
        return cls._instance
    def __init__(self):
        """
        Inicializador da instância. Em um singleton, este método pode ser chamado
        múltiplas vezes se o __new__ não for estritamente controlado.
        Usamos `_initialized` para garantir que a lógica de inicialização seja executada apenas uma vez.
        """
        if self._initialized:
            # Se já inicializado, não faz nada para evitar duplicação de setup.
            return
        
        self.logger.debug("DatabaseManager: Executando inicialização única da instância.")
        # O pool e a URL do DB já são atributos de classe, mas podemos reconfirmar.
        # self._pool = None 
        # self._db_url = None
        self._initialized = True # Marca como inicializado após a primeira vez

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        """
        Método de fábrica de classe para obter a única instância do DatabaseManager.
        Este é o ponto de acesso recomendado para obter o gerenciador de DB.
        """
        return cls.__new__(cls) # Chama __new__ que garante o singleton

    async def connect(self, db_url: str):
        """
        Cria e inicializa o pool de conexões com o banco de dados.
        Este método é idempotente: só criará o pool se ele não existir ou
        tiver sido explicitamente fechado.

        Args:
            db_url (str): A URL de conexão do banco de dados (DSN).
                          Ex: "postgresql://user:password@host:port/dbname"
        Raises:
            ValueError: Se db_url for nulo ou vazio.
            Exception: Em caso de falha crítica na conexão com o banco de dados.
        """
        if self._pool and not self._pool._closed:
            self.logger.info("DatabaseManager: Pool de conexões já está ativo e pronto. Nenhuma ação necessária.")
            return

        if not db_url:
            raise ValueError("A URL do banco de dados (db_url) não pode ser nula ou vazia para a conexão.")
        
        self._db_url = db_url
        # Para fins de log, esconde a senha da URL do banco de dados
        log_url = self._db_url.split('@')[-1] if '@' in self._db_url else self._db_url
        self.logger.info(f"DatabaseManager: Tentando criar pool de conexões para {log_url}...")
        
        try:
            self._pool = await asyncpg.create_pool(
                dsn=self._db_url,
                min_size=1,        # Número mínimo de conexões a serem mantidas no pool
                max_size=20,       # Número máximo de conexões no pool
                timeout=60,        # Tempo máximo em segundos para esperar por uma conexão do pool
                max_queries=50000, # Fechar e reabrir uma conexão após 50k consultas (para evitar vazamentos)
                # command_timeout=30 # Tempo limite para cada comando SQL
                loop=None          # Usa o loop de eventos padrão (asyncio.get_event_loop())
            )
            self.logger.info("DatabaseManager: Pool de conexões asyncpg criado com sucesso.")
        except asyncpg.exceptions.InvalidCatalogNameError:
            self.logger.critical(f"DatabaseManager: Erro: Banco de dados '{self._db_url.split('/')[-1]}' não existe. Crie o banco de dados primeiro.")
            raise
        except asyncpg.exceptions.ConnectionDoesNotExistError:
            self.logger.critical("DatabaseManager: Erro de conexão: Host ou porta inacessível.")
            raise
        except Exception as e:
            self.logger.critical(f"DatabaseManager: FALHA CRÍTICA ao criar pool de conexões: {e}", exc_info=True)
            # Re-lança a exceção para que o startup da aplicação falhe,
            # o que é o comportamento correto para um erro crítico de conexão.
            raise

    async def close(self):
        """
        Fecha o pool de conexões de forma segura.
        Este método é idempotente: só tentará fechar o pool se ele estiver ativo.
        """
        if self._pool and not self._pool._closed:
            self.logger.info("DatabaseManager: Fechando pool de conexões...")
            try:
                await self._pool.close()
                self._pool = None # Limpa a referência após fechar
                self.logger.info("DatabaseManager: Pool de conexões fechado com sucesso.")
            except Exception as e:
                self.logger.error(f"DatabaseManager: Erro ao tentar fechar o pool de conexões: {e}", exc_info=True)
        else:
            self.logger.info("DatabaseManager: Nenhum pool de conexões ativo para fechar. Nenhuma ação necessária.")

    def get_connection(self) -> ContextManager[asyncpg.Connection]:
        """
        Retorna um gerenciador de contexto assíncrono para obter uma conexão do pool.
        Esta conexão é automaticamente liberada de volta para o pool ao sair do bloco 'async with'.

        Raises:
            ConnectionError: Se o pool de conexões não estiver inicializado ou estiver fechado.

        Returns:
            ContextManager[asyncpg.Connection]: Um gerenciador de contexto para uma conexão asyncpg.

        Exemplo de uso:
            db_manager = DatabaseManager.get_instance()
            async with db_manager.get_connection() as conn:
                result = await conn.fetch("SELECT 1")
        """
        if not self.is_connected:
            self.logger.error("DatabaseManager: Tentativa de obter conexão sem um pool ativo. Verifique o ciclo de vida da aplicação.")
            raise ConnectionError("O pool de conexões não está inicializado ou foi fechado. Chame 'connect()' primeiro.")
        
        # asyncpg.Pool.acquire() é um gerenciador de contexto assíncrono
        return self._pool.acquire()

    @property
    def is_connected(self) -> bool:
        """
        Propriedade para verificar o estado atual do pool de conexões.

        Returns:
            bool: True se o pool estiver ativo e não fechado, False caso contrário.
        """
        # A propriedade interna _closed do asyncpg.Pool indica se o pool foi fechado
        return self._pool is not None and not self._pool._closed