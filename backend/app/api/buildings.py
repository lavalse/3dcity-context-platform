"""
Buildings API — geometry endpoints for the map tab.

GET /api/buildings?bbox=minLon,minLat,maxLon,maxLat
    Returns a GeoJSON FeatureCollection of building envelopes in the viewport.
    Max 3000 buildings per request; truncated=true if exceeded.

GET /api/buildings/{gmlid}
    Returns attributes + LOD1 geometry + LOD2 thematic surfaces for one building.

Note: All geometry queries use ST_FlipCoordinates() because 3DCityDB stores
coordinates in (lat, lon) order (JGD2011 axis convention), but GeoJSON requires
(lon, lat) order.
"""

import json
import asyncio
from fastapi import APIRouter, HTTPException, Query

from app.database import get_pool

router = APIRouter()

# Taito-ku full extent (lon, lat)
TAITO_BBOX = (139.757, 35.695, 139.815, 35.740)

USAGE_LABELS = {
    "401": "業務施設",
    "402": "商業施設",
    "403": "宿泊施設",
    "404": "商業系複合施設",
    "411": "住宅",
    "412": "共同住宅",
    "413": "店舗等併用住宅",
    "414": "店舗等併用共同住宅",
    "415": "作業所併用住宅",
    "421": "官公庁施設",
    "422": "文教厚生施設",
    "431": "運輸倉庫施設",
    "441": "工場",
    "454": "その他",
    "461": "不明",
}


@router.get("/buildings")
async def get_buildings(
    bbox: str = Query(
        default=None,
        description="minLon,minLat,maxLon,maxLat in WGS84/JGD2011",
    )
):
    """Return building envelopes as GeoJSON FeatureCollection for the given bbox."""
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError()
            min_lon, min_lat, max_lon, max_lat = parts
        except ValueError:
            raise HTTPException(status_code=400, detail="bbox must be minLon,minLat,maxLon,maxLat")
    else:
        min_lon, min_lat, max_lon, max_lat = TAITO_BBOX

    sql = """
        SELECT
            co.gmlid,
            COALESCE(b.measured_height, 0)  AS measured_height,
            b.usage,
            b.storeys_above_ground,
            (b.lod2_solid_id IS NOT NULL)   AS has_lod2,
            ST_AsGeoJSON(ST_FlipCoordinates(co.envelope), 15, 0) AS geom_json
        FROM citydb.building b
        JOIN citydb.cityobject co ON co.id = b.id
        WHERE b.building_root_id = b.id
          AND co.envelope IS NOT NULL
          AND ST_FlipCoordinates(co.envelope) && ST_MakeEnvelope($1, $2, $3, $4, 6668)
        LIMIT 3001
    """

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await asyncio.wait_for(
                conn.fetch(sql, min_lon, min_lat, max_lon, max_lat),
                timeout=15,
            )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Query timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    truncated = len(rows) > 3000
    features = []
    for row in rows[:3000]:
        geom = json.loads(row["geom_json"])
        # envelope is a 3D bbox polygon — drop Z for simpler GeoJSON
        if geom.get("coordinates"):
            geom["coordinates"] = [
                [[c[0], c[1]] for c in ring]
                for ring in geom["coordinates"]
            ]
        height = float(row["measured_height"]) if row["measured_height"] else 0
        if height <= 0:
            height = 3.0  # default 3m for unmeasured buildings
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "gmlid": row["gmlid"],
                "measured_height": height,
                "usage": row["usage"],
                "usage_label": USAGE_LABELS.get(row["usage"] or "", "不明"),
                "storeys_above_ground": row["storeys_above_ground"],
                "has_lod2": bool(row["has_lod2"]),
            },
        })

    return {
        "type": "FeatureCollection",
        "truncated": truncated,
        "count": len(features),
        "features": features,
    }


@router.get("/buildings/{gmlid}")
async def get_building_detail(gmlid: str):
    """Return attributes + LOD1 + LOD2 geometry for a single building."""
    pool = await get_pool()

    # --- 1. Attributes ---
    attr_sql = """
        SELECT
            co.gmlid,
            b.measured_height,
            b.storeys_above_ground,
            b.storeys_below_ground,
            b.usage,
            b.class,
            (b.lod2_solid_id IS NOT NULL) AS has_lod2
        FROM citydb.building b
        JOIN citydb.cityobject co ON co.id = b.id
        WHERE co.gmlid = $1 AND b.building_root_id = b.id
        LIMIT 1
    """

    # --- 2. LOD1 geometry ---
    lod1_sql = """
        SELECT ST_AsGeoJSON(ST_FlipCoordinates(sg.geometry), 15, 0) AS geom_json
        FROM citydb.building b
        JOIN citydb.cityobject co ON co.id = b.id
        JOIN citydb.surface_geometry sg ON sg.root_id = b.lod1_solid_id
        WHERE co.gmlid = $1
          AND sg.geometry IS NOT NULL
    """

    # --- 3. LOD2 thematic surfaces ---
    lod2_sql = """
        SELECT
            ts.objectclass_id,
            ST_AsGeoJSON(ST_FlipCoordinates(sg.geometry), 15, 0) AS geom_json
        FROM citydb.building b
        JOIN citydb.cityobject co ON co.id = b.id
        JOIN citydb.thematic_surface ts ON ts.building_id = b.id
        JOIN citydb.surface_geometry sg ON sg.root_id = ts.lod2_multi_surface_id
        WHERE co.gmlid = $1
          AND sg.geometry IS NOT NULL
    """

    try:
        async with pool.acquire() as conn:
            attr_rows = await conn.fetch(attr_sql, gmlid)
            lod1_rows = await conn.fetch(lod1_sql, gmlid)
            lod2_rows = await conn.fetch(lod2_sql, gmlid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not attr_rows:
        raise HTTPException(status_code=404, detail=f"Building not found: {gmlid}")

    attr = attr_rows[0]

    # Build LOD1 FeatureCollection (drop Z for 2D map rendering)
    def make_feature(geom_json: str, props: dict = None) -> dict:
        geom = json.loads(geom_json)
        # Keep Z coordinates for LOD surfaces (useful for 3D context)
        return {"type": "Feature", "geometry": geom, "properties": props or {}}

    lod1_fc = {
        "type": "FeatureCollection",
        "features": [make_feature(r["geom_json"]) for r in lod1_rows],
    }

    # Split LOD2 surfaces by type
    # objectclass_id: 33=Wall, 34=Roof, 35=Ground
    wall_features, roof_features, ground_features = [], [], []
    for r in lod2_rows:
        feat = make_feature(r["geom_json"], {"surface_type": r["objectclass_id"]})
        oc = r["objectclass_id"]
        if oc == 33:
            wall_features.append(feat)
        elif oc == 34:
            roof_features.append(feat)
        elif oc == 35:
            ground_features.append(feat)

    def fc(features):
        return {"type": "FeatureCollection", "features": features}

    return {
        "gmlid": attr["gmlid"],
        "attributes": {
            "measured_height": float(attr["measured_height"]) if attr["measured_height"] else None,
            "usage": attr["usage"],
            "usage_label": USAGE_LABELS.get(attr["usage"] or "", "不明"),
            "storeys_above_ground": (
                attr["storeys_above_ground"]
                if attr["storeys_above_ground"] and attr["storeys_above_ground"] != 9999
                else None
            ),
            "storeys_below_ground": (
                attr["storeys_below_ground"]
                if attr["storeys_below_ground"] and attr["storeys_below_ground"] != 9999
                else None
            ),
            "class": attr["class"],
            "has_lod2": bool(attr["has_lod2"]),
        },
        "lod1": lod1_fc,
        "lod2": {
            "wall": fc(wall_features),
            "roof": fc(roof_features),
            "ground": fc(ground_features),
        },
    }
