"""
Export API — returns GeoJSON FeatureCollection for selected features.

POST /api/export
  Body: {"items": [{"gmlid": "...", "type": "building|land_use|road|flood_zone"}, ...]}
  Response: GeoJSON FeatureCollection (RFC 7946)

Geometry is read from pre-built materialized views (WGS84 / EPSG:4326),
so coordinates are not tile-clipped and represent the full feature geometry.
"""

import json
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_pool

router = APIRouter()

# Materialized view names and their attribute columns per feature type
_VIEW_CONFIG: dict[str, tuple[str, list[str]]] = {
    "building":    ("citydb.building_footprints",   ["gmlid", "measured_height", "usage", "has_lod2"]),
    "land_use":    ("citydb.land_use_footprints",    ["gmlid", "class", "usage"]),
    "road":        ("citydb.road_footprints",        ["gmlid", "class", "function", "usage"]),
    "flood_zone":  ("citydb.flood_zone_footprints",  ["gmlid", "class", "function", "usage"]),
    "bridge":      ("citydb.bridge_footprints",      ["gmlid", "class", "function", "usage"]),
    "furniture":   ("citydb.furniture_footprints",   ["gmlid", "class", "function", "usage"]),
    "vegetation":  ("citydb.vegetation_footprints",  ["gmlid", "class", "usage"]),
}


class ExportItem(BaseModel):
    gmlid: str
    type: Literal["building", "land_use", "road", "flood_zone", "bridge", "furniture", "vegetation"]


class ExportRequest(BaseModel):
    items: list[ExportItem]


@router.post("/export")
async def export_geojson(body: ExportRequest):
    """Return a GeoJSON FeatureCollection for the requested features."""
    if not body.items:
        return {"type": "FeatureCollection", "features": []}

    if len(body.items) > 2000:
        raise HTTPException(status_code=400, detail="Too many items (max 2000)")

    # Group gmlids by type
    by_type: dict[str, list[str]] = {}
    for item in body.items:
        by_type.setdefault(item.type, []).append(item.gmlid)

    pool = await get_pool()
    features: list[dict] = []

    try:
        async with pool.acquire() as conn:
            for ftype, gmlids in by_type.items():
                view, attr_cols = _VIEW_CONFIG[ftype]
                # Build SELECT: all attr cols + geometry as GeoJSON
                cols = ", ".join(attr_cols)
                sql = f"""
                    SELECT {cols}, ST_AsGeoJSON(geometry) AS geom
                    FROM {view}
                    WHERE gmlid = ANY($1)
                """
                rows = await conn.fetch(sql, gmlids)
                for row in rows:
                    props = {col: row[col] for col in attr_cols}
                    # Convert non-serialisable types (e.g. asyncpg Decimal → float)
                    for k, v in props.items():
                        if isinstance(v, Decimal):
                            props[k] = float(v)
                        elif v is not None and not isinstance(v, (str, int, float, bool)):
                            props[k] = str(v)
                    props["feature_type"] = ftype
                    features.append({
                        "type": "Feature",
                        "geometry": json.loads(row["geom"]),
                        "properties": props,
                    })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"type": "FeatureCollection", "features": features}
