"""
Census Areas API — administrative boundary endpoints.

GET /api/areas                    — List all ~200 census tracts (key_code, moji, s_area)
GET /api/areas/by-name            — Search by Japanese name (?q=上野)
GET /api/areas/{key_code}         — Single area attrs + GeoJSON boundary polygon
GET /api/areas/{key_code}/stats   — Spatial counts: buildings, vegetation, roads
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi import Query as QueryParam

from app.database import get_pool

router = APIRouter()


@router.get("/areas/by-name")
async def search_areas_by_name(q: str = QueryParam(..., description="Japanese area name (partial match)")):
    """Search census tracts by Japanese name (moji)."""
    sql = """
        SELECT key_code, moji, s_area, city
        FROM citydb.census_boundaries
        WHERE moji LIKE $1
        ORDER BY moji
        LIMIT 50
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, f"%{q}%")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"areas": [dict(r) for r in rows], "count": len(rows)}


@router.get("/areas")
async def list_areas():
    """Return all census tracts with key_code, moji, s_area."""
    sql = """
        SELECT key_code, moji, s_area, city
        FROM citydb.census_boundaries
        ORDER BY key_code
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"areas": [dict(r) for r in rows], "count": len(rows)}


@router.get("/areas/{key_code}/stats")
async def get_area_stats(key_code: str):
    """Return spatial counts of buildings, vegetation, and roads within an area."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            area = await conn.fetchrow(
                "SELECT key_code, moji, ST_AsGeoJSON(geometry, 8, 0) AS geom_json FROM citydb.census_boundaries WHERE key_code = $1",
                key_code,
            )
            if not area:
                raise HTTPException(status_code=404, detail=f"Area not found: {key_code}")

            geom_wkt = await conn.fetchval(
                "SELECT ST_AsText(geometry) FROM citydb.census_boundaries WHERE key_code = $1",
                key_code,
            )

            buildings = await conn.fetchval(
                "SELECT COUNT(*) FROM citydb.building_footprints bf WHERE ST_Within(bf.geometry, ST_GeomFromText($1, 4326))",
                geom_wkt,
            )

            # Usage breakdown for buildings within this area
            usage_rows = await conn.fetch(
                """
                SELECT bf.usage, COUNT(*) AS cnt
                FROM citydb.building_footprints bf
                WHERE ST_Within(bf.geometry, ST_GeomFromText($1, 4326))
                  AND bf.usage IS NOT NULL
                GROUP BY bf.usage
                ORDER BY cnt DESC
                """,
                geom_wkt,
            )

            avg_height = await conn.fetchval(
                """
                SELECT ROUND(AVG(bf.measured_height)::numeric, 1)
                FROM citydb.building_footprints bf
                WHERE ST_Within(bf.geometry, ST_GeomFromText($1, 4326))
                  AND bf.measured_height > 0
                """,
                geom_wkt,
            )

            vegetation = await conn.fetchval(
                "SELECT COUNT(*) FROM citydb.vegetation_footprints vf WHERE ST_Within(vf.geometry, ST_GeomFromText($1, 4326))",
                geom_wkt,
            )

            roads = await conn.fetchval(
                "SELECT COUNT(*) FROM citydb.road_footprints rf WHERE ST_Within(rf.geometry, ST_GeomFromText($1, 4326))",
                geom_wkt,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "key_code": area["key_code"],
        "moji": area["moji"],
        "counts": {
            "buildings": buildings,
            "vegetation": vegetation,
            "roads": roads,
        },
        "building_usage_breakdown": [{"usage": r["usage"], "count": r["cnt"]} for r in usage_rows],
        "avg_building_height_m": float(avg_height) if avg_height is not None else None,
    }


@router.get("/areas/{key_code}/buildings")
async def export_area_buildings(key_code: str):
    """Return GeoJSON FeatureCollection of all building footprints within the area."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            area = await conn.fetchrow(
                "SELECT key_code, moji FROM citydb.census_boundaries WHERE key_code = $1",
                key_code,
            )
            if not area:
                raise HTTPException(status_code=404, detail=f"Area not found: {key_code}")

            geom_wkt = await conn.fetchval(
                "SELECT ST_AsText(geometry) FROM citydb.census_boundaries WHERE key_code = $1",
                key_code,
            )

            rows = await conn.fetch(
                """
                SELECT bf.gmlid, bf.measured_height, bf.usage,
                       ST_AsGeoJSON(bf.geometry, 8, 0) AS geom_json
                FROM citydb.building_footprints bf
                WHERE ST_Within(bf.geometry, ST_GeomFromText($1, 4326))
                """,
                geom_wkt,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "geometry": json.loads(r["geom_json"]),
            "properties": {
                "gmlid": r["gmlid"],
                "measured_height": r["measured_height"],
                "usage": r["usage"],
            },
        })

    fc = json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False)
    moji = area["moji"] or key_code
    from urllib.parse import quote
    from fastapi.responses import Response
    encoded_name = quote(f"{moji}_buildings.geojson", safe="")
    return Response(
        content=fc,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )


@router.get("/areas/{key_code}")
async def get_area_detail(key_code: str):
    """Return attrs + GeoJSON boundary polygon for a single census tract."""
    sql = """
        SELECT key_code, pref, city, s_area, moji, kcode1,
               ST_AsGeoJSON(geometry, 8, 0) AS geom_json
        FROM citydb.census_boundaries
        WHERE key_code = $1
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, key_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not row:
        raise HTTPException(status_code=404, detail=f"Area not found: {key_code}")

    return {
        "key_code": row["key_code"],
        "pref": row["pref"],
        "city": row["city"],
        "s_area": row["s_area"],
        "moji": row["moji"],
        "kcode1": row["kcode1"],
        "geometry": json.loads(row["geom_json"]),
    }
