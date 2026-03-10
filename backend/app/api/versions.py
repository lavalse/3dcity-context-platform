"""
Version history endpoints.

GET /api/buildings/{gmlid}/versions  — version history for a building
GET /api/features/{gmlid}/versions   — version history for any feature
"""

from fastapi import APIRouter, HTTPException

from app.database import get_pool

router = APIRouter()


async def _get_versions(gmlid: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT version, status, source_tag, change_type,
                   attributes, changed_at, change_note
            FROM citydb.feature_versions
            WHERE gmlid = $1
            ORDER BY version DESC
            """,
            gmlid,
        )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No version history for: {gmlid}")

    return {
        "gmlid": gmlid,
        "versions": [
            {
                "version":     r["version"],
                "status":      r["status"],
                "source_tag":  r["source_tag"],
                "change_type": r["change_type"],
                "attributes":  r["attributes"],
                "changed_at":  r["changed_at"].isoformat() if r["changed_at"] else None,
                "change_note": r["change_note"],
            }
            for r in rows
        ],
    }


@router.get("/buildings/{gmlid}/versions")
async def get_building_versions(gmlid: str):
    """Return all versions of a building, newest first."""
    return await _get_versions(gmlid)


@router.get("/features/{gmlid}/versions")
async def get_feature_versions(gmlid: str):
    """Return all versions of any feature, newest first."""
    return await _get_versions(gmlid)
