# app/api/routers/health.py
import logging
from fastapi import APIRouter, HTTPException, status, Depends # <-- Importe Depends

# IMPORTANTE: Importe a função de dependência, não a variável global diretamente
from ..dependencies import get_db_manager # <-- AQUI ESTÁ A MUDANÇA CRÍTICA

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Verifica a saúde da API",
    description="Retorna o status 'ok' se a API estiver funcionando corretamente e acessível. Verifica a conectividade do banco de dados para um status mais completo."
)
# Use a injeção de dependência para obter o db_manager
async def health_check(db_manager_dep = Depends(get_db_manager)): # <-- Mude esta linha
    """
    Endpoint para verificação de saúde da aplicação. Não requer autenticação.
    Verifica a conectividade do banco de dados para um status mais completo.
    """
    try:
        # db_manager_dep agora é a instância do DatabaseManager fornecida pela dependência
        conn = await db_manager_dep.get_connection() 
        await db_manager_dep.put_connection(conn)    
        db_status = "ok"
        
        return {"status": "ok", "message": "API is running and healthy", "database_status": db_status}
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        # Note: Se db_manager_dep fosse None aqui, isso já teria levantado um HTTPException em get_db_manager
        # mas mantemos o catch para outros erros de conexão/operação do DB
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"API is unhealthy: {e}")