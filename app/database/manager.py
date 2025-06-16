# app/database/manager.py

import psycopg2
from psycopg2 import pool
# Importar a instância 'settings' do seu módulo de configurações

from app.config.settings import settings # <-- IMPORTANTE: Use a instância global de settings
import logging # Adicionar logging para depuração e mensagens

# Configurar logging para este módulo
logger = logging.getLogger(__name__)

# REMOVA estas linhas, pois settings já carrega o .env
# import os
# from dotenv import load_dotenv
# load_dotenv()


class DatabaseManager:
    """
    Gerencia o pool de conexões com o banco de dados PostgreSQL.
    Implementa o padrão Singleton para o pool de conexões.
    """
    _connection_pool = None

    def __init__(self):
        """
        Inicializa o DatabaseManager. Se o pool de conexões ainda não foi criado,
        ele é inicializado. Isso garante que o pool seja configurado apenas uma vez.
        """
        if DatabaseManager._connection_pool is None:
            try:
                self._init_pool()
                logger.info("Pool de conexões PostgreSQL inicializado com sucesso.") # Use logger.info
            except Exception as e:
                logger.error(f"Erro ao inicializar o pool de conexões do PostgreSQL: {e}") # Use logger.error
                raise # Re-lança a exceção para que a aplicação falhe se a conexão for crítica

    @classmethod
    def _init_pool(cls):
        """
        Método de classe para inicializar o pool de conexões.
        Utiliza variáveis de ambiente para a configuração do banco de dados.
        """
        try:
            # Prepare os parâmetros da conexão usando a instância settings
            conn_params = {
                'host': settings.DB_HOST,
                'database': settings.DB_NAME,
                'user': settings.DB_USER,
                'password': settings.DB_PASSWORD,
                'port': settings.DB_PORT,
                'client_encoding': 'UTF8' # Adicione esta linha para garantir UTF8 no cliente
            }

            # --- LINHAS DE DEBUG (Temporárias para identificar a DSN) ---
            dsn_parts = []
            for key, value in conn_params.items():
                if key == 'password':
                    dsn_parts.append(f"{key}=******") # Esconda a senha no log de produção
                else:
                    dsn_parts.append(f"{key}={value}")
            
            dsn_string_for_debug = " ".join(dsn_parts)
            logger.info(f"DEBUG DSN String: '{dsn_string_for_debug}'")
            try:
                logger.info(f"DEBUG DSN Bytes (UTF-8 hex): {dsn_string_for_debug.encode('utf-8').hex()}")
            except UnicodeEncodeError as uee:
                logger.error(f"ERRO ao tentar codificar DSN para bytes (UTF-8): {uee}")
                # Se esta linha falhar, significa que a string DSN já está com caracteres inválidos em algum encoding Python.
                # Podemos tentar inspecionar o valor original lido pelo Pydantic Settings.
            # --- FIM DAS LINHAS DE DEBUG ---

            cls._connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                **conn_params # Passa os parâmetros como kwargs
            )
            logger.info("Pool de conexões do PostgreSQL inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao inicializar o pool de conexões do PostgreSQL: {e}")
            raise # Re-lança a exceção

    def get_connection(self):
        """
        Obtém uma conexão do pool.
        """
        if DatabaseManager._connection_pool is None:
            self._init_pool()
        return DatabaseManager._connection_pool.getconn()

    def return_connection(self, conn):
        """
        Retorna uma conexão para o pool, liberando-a para reuso.
        """
        if DatabaseManager._connection_pool:
            DatabaseManager._connection_pool.putconn(conn)

    @classmethod
    def close_pool(cls):
        """
        Fecha todas as conexões no pool. Deve ser chamado ao encerrar a aplicação
        para liberar os recursos do banco de dados.
        """
        if cls._connection_pool:
            cls._connection_pool.closeall()
            cls._connection_pool = None
            logger.info("Pool de conexões do PostgreSQL fechado.")

    def initialize_db(self):
        """
        Verifica e cria a tabela 'validacoes_telefone' se ela não existir.
        Esta função é idempotente (pode ser chamada múltiplas vezes sem causar erro).
        Inclui as colunas `is_deleted` e `deleted_at` para a funcionalidade de soft delete.
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS validacoes_telefone (
                    id SERIAL PRIMARY KEY,
                    input_data_original TEXT NOT NULL,
                    input_data_cleaned TEXT,
                    valido BOOLEAN NOT NULL,
                    mensagem TEXT,
                    origem_validacao TEXT,
                    tipo_telefone TEXT,
                    data_validacao TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    app_name TEXT,
                    client_identifier TEXT,
                    regra_codigo TEXT,
                    validation_details JSONB,
                    is_deleted BOOLEAN DEFAULT FALSE,
                    deleted_at TIMESTAMP WITH TIME ZONE
                );
            """)
            conn.commit()
            cursor.close()
            logger.info("Banco de dados e tabela 'validacoes_telefone' verificados/inicializados com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao inicializar o banco de dados: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.return_connection(conn)