import asyncpg
import asyncio
import re
from typing import Any
from contextlib import asynccontextmanager

from app.config import get_settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        # asyncpg uses its own DSN format (not SQLAlchemy)
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


class QueryError(Exception):
    pass


def _validate_sql(sql: str) -> str:
    """Reject anything that isn't a SELECT. Strip trailing semicolons."""
    cleaned = sql.strip().rstrip(";")
    first_word = cleaned.lstrip().split()[0].upper() if cleaned.strip() else ""
    if first_word != "SELECT":
        raise QueryError("Only SELECT queries are allowed.")
    # Block stacked queries
    if ";" in cleaned:
        raise QueryError("Multiple statements are not allowed.")
    return cleaned


def _inject_limit(sql: str, limit: int) -> str:
    """Add LIMIT if the query doesn't already have one."""
    if re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
        return sql
    return f"{sql}\nLIMIT {limit}"


async def run_query(sql: str) -> dict[str, Any]:
    """
    Validate and execute a SQL query safely.
    Returns: {columns, rows, row_count}
    Raises: QueryError on validation failure or DB error.
    """
    settings = get_settings()

    try:
        safe_sql = _validate_sql(sql)
        safe_sql = _inject_limit(safe_sql, settings.query_row_limit)
    except QueryError:
        raise

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            result = await asyncio.wait_for(
                conn.fetch(safe_sql),
                timeout=settings.query_timeout_seconds,
            )
    except asyncio.TimeoutError:
        raise QueryError(f"Query timed out after {settings.query_timeout_seconds} seconds.")
    except asyncpg.PostgresError as e:
        raise QueryError(f"Database error: {e}")

    if not result:
        return {"columns": [], "rows": [], "row_count": 0}

    columns = list(result[0].keys())
    rows = [list(row.values()) for row in result]
    return {"columns": columns, "rows": rows, "row_count": len(rows)}
