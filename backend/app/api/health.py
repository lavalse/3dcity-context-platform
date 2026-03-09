import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.database import get_pool
from app.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health():
    settings = get_settings()
    db_ok = False
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
    except Exception as e:
        logger.warning("Health check: DB unreachable: %s", e)

    llm_mode = "claude_api" if settings.use_llm else "placeholder"
    if not db_ok:
        return JSONResponse(status_code=503, content={
            "status": "degraded",
            "db": "unreachable",
            "llm_mode": llm_mode,
        })
    return {"status": "ok", "db": "connected", "llm_mode": llm_mode}
