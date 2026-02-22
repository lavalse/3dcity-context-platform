from fastapi import APIRouter
from app.database import get_pool
from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health():
    settings = get_settings()
    db_ok = False
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "db": "connected" if db_ok else "unreachable",
        "llm_mode": "claude_api" if settings.use_llm else "placeholder",
    }
