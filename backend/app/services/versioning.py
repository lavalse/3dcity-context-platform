"""
Lightweight versioning helpers for city features.

Call archive_and_next_version() + insert_version() inside an existing
asyncpg transaction connection to atomically record a change.
"""

import decimal
import json


class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super().default(o)


async def archive_and_next_version(conn, gmlid: str) -> int:
    """
    Mark the current version of gmlid as 'archived' and return the next version number.
    If no version exists yet, returns 1 (first version).
    """
    # Serialize version assignment per feature to avoid duplicate MAX(version)+1
    # results under concurrent writes for the same gmlid.
    await conn.fetchval(
        "SELECT pg_advisory_xact_lock(hashtext($1), 0)",
        gmlid,
    )
    await conn.execute(
        "UPDATE citydb.feature_versions SET status = 'archived' "
        "WHERE gmlid = $1 AND status = 'current'",
        gmlid,
    )
    next_ver = await conn.fetchval(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM citydb.feature_versions WHERE gmlid = $1",
        gmlid,
    )
    return next_ver


async def insert_version(
    conn,
    gmlid: str,
    version: int,
    change_type: str,
    attributes: dict,
    source_tag: str = "manual-edit",
    note: str | None = None,
    status: str = "current",
):
    """Insert a new version record for gmlid."""
    await conn.execute(
        """
        INSERT INTO citydb.feature_versions
            (gmlid, version, status, source_tag, change_type, attributes, change_note)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        gmlid,
        version,
        status,
        source_tag,
        change_type,
        json.dumps(attributes, cls=_Encoder),
        note,
    )
