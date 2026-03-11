"""
Shelter Facilities API — 避難施設 endpoints.

GET /api/shelters                        — list all (filter: ?level=1|2|3)
GET /api/shelters/coverage               — buildings ranked by distance to nearest shelter
GET /api/shelters/{id}                   — detail + GeoJSON point
GET /api/shelters/{id}/nearest-buildings — nearest buildings by distance (default limit=20)
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi import Query as QueryParam

from app.database import get_pool

router = APIRouter()


@router.get("/shelters/coverage")
async def shelter_coverage(limit: int = QueryParam(default=50, ge=1, le=500)):
    """Return buildings ranked by distance to their nearest shelter (furthest first)."""
    sql = """
        SELECT bf.gmlid, bf.usage, bf.measured_height,
               ROUND(nn.dist_m::numeric, 1) AS nearest_shelter_m
        FROM citydb.building_footprints bf
        CROSS JOIN LATERAL (
            SELECT ST_Distance(bf.geometry::geography, s.geometry::geography) AS dist_m
            FROM citydb.shelter_facilities s
            ORDER BY s.geometry::geography <-> bf.geometry::geography
            LIMIT 1
        ) nn
        WHERE bf.measured_height > 0
        ORDER BY nn.dist_m DESC
        LIMIT $1
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "buildings": [dict(r) for r in rows],
        "count": len(rows),
    }


@router.get("/shelters")
async def list_shelters(level: int | None = QueryParam(default=None, ge=1, le=3)):
    """Return all shelter facilities (optionally filtered by level 1/2/3)."""
    if level is not None:
        sql = """
            SELECT id, name, address, level, capacity, disaster_types,
                   facility_type, facility_area, district, height,
                   ST_AsGeoJSON(geometry, 8, 0) AS geom_json
            FROM citydb.shelter_facilities
            WHERE level = $1
            ORDER BY id
        """
        params = [level]
    else:
        sql = """
            SELECT id, name, address, level, capacity, disaster_types,
                   facility_type, facility_area, district, height,
                   ST_AsGeoJSON(geometry, 8, 0) AS geom_json
            FROM citydb.shelter_facilities
            ORDER BY id
        """
        params = []

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    shelters = []
    for r in rows:
        d = dict(r)
        d["geometry"] = json.loads(d.pop("geom_json"))
        shelters.append(d)
    return {"shelters": shelters, "count": len(shelters)}


@router.get("/shelters/{shelter_id}/nearest-buildings")
async def shelter_nearest_buildings(
    shelter_id: int,
    limit: int = QueryParam(default=20, ge=1, le=100),
):
    """Return buildings nearest to a shelter, ordered by distance (metres)."""
    sql = """
        SELECT bf.gmlid, bf.usage, bf.measured_height,
               ROUND(ST_Distance(bf.geometry::geography, s.geometry::geography)::numeric, 1)
                   AS dist_m
        FROM citydb.shelter_facilities s
        CROSS JOIN LATERAL (
            SELECT bf.gmlid, bf.usage, bf.measured_height, bf.geometry
            FROM citydb.building_footprints bf
            ORDER BY bf.geometry::geography <-> s.geometry::geography
            LIMIT $2
        ) bf
        WHERE s.id = $1
        ORDER BY dist_m
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, shelter_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not rows and (await _shelter_exists(shelter_id)):
        pass  # valid shelter but no nearby buildings found
    return {"buildings": [dict(r) for r in rows], "count": len(rows)}


@router.get("/shelters/{shelter_id}")
async def get_shelter(shelter_id: int):
    """Return detail + GeoJSON point for a single shelter."""
    sql = """
        SELECT id, name, address, level, capacity, disaster_types,
               facility_type, facility_area, district, height,
               ST_AsGeoJSON(geometry, 8, 0) AS geom_json
        FROM citydb.shelter_facilities
        WHERE id = $1
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, shelter_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not row:
        raise HTTPException(status_code=404, detail=f"Shelter not found: {shelter_id}")
    d = dict(row)
    d["geometry"] = json.loads(d.pop("geom_json"))
    return d


async def _shelter_exists(shelter_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM citydb.shelter_facilities WHERE id = $1)",
            shelter_id,
        )
