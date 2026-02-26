"""
Buildings API — geometry endpoints for the map tab.

GET /api/buildings/{gmlid}
    Returns attributes + LOD1 geometry + LOD2 thematic surfaces for one building.

Note: All geometry queries use ST_FlipCoordinates() because 3DCityDB stores
coordinates in (lat, lon) order (JGD2011 axis convention), but GeoJSON requires
(lon, lat) order.

Building footprints for the map overview are served as MVT vector tiles by Martin,
not by this API. See data/migrations/001_building_footprints_mv.sql.
"""

import json
from fastapi import APIRouter, HTTPException

from app.database import get_pool

router = APIRouter()

CLASS_LABELS = {
    "3001": "普通建物",
    "3002": "堅牢建物",
    "3003": "普通無壁舎",
    "3004": "堅牢無壁舎",
    "9999": "不明",
}

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


@router.get("/buildings/{gmlid}")
async def get_building_detail(gmlid: str):
    """Return attributes + LOD1 + LOD2 geometry for a single building."""
    pool = await get_pool()

    # --- 1. Attributes ---
    attr_sql = """
        SELECT
            co.gmlid,
            co.name,
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

    # --- 4. Generic attributes (uro: ADE overflow attributes) ---
    generic_sql = """
        SELECT ga.attrname, ga.datatype, ga.strval, ga.intval, ga.realval
        FROM citydb.cityobject_genericattrib ga
        JOIN citydb.building b ON b.id = ga.cityobject_id
        JOIN citydb.cityobject co ON co.id = b.id
        WHERE co.gmlid = $1
        ORDER BY ga.attrname
    """

    # --- 2. LOD1 geometry — return single 2D footprint polygon ---
    # Collect all solid faces, project to 2D, then take convex hull → building footprint.
    lod1_sql = """
        SELECT ST_AsGeoJSON(
            ST_FlipCoordinates(ST_ConvexHull(ST_Collect(ST_Force2D(sg.geometry)))),
            15, 0
        ) AS geom_json
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
            generic_rows = await conn.fetch(generic_sql, gmlid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not attr_rows:
        raise HTTPException(status_code=404, detail=f"Building not found: {gmlid}")

    attr = attr_rows[0]

    def make_feature(geom_json: str, props: dict = None) -> dict:
        geom = json.loads(geom_json)
        return {"type": "Feature", "geometry": geom, "properties": props or {}}

    # Height used for fill-extrusion in the frontend
    lod1_height = (
        float(attr["measured_height"])
        if attr["measured_height"] and float(attr["measured_height"]) > 0
        else 10.0
    )

    lod1_fc = {
        "type": "FeatureCollection",
        "features": [make_feature(r["geom_json"], {"height": lod1_height}) for r in lod1_rows],
    }

    # Split LOD2 surfaces by type
    # Verified against citydb.objectclass: 33=BuildingRoofSurface, 34=BuildingWallSurface, 35=BuildingGroundSurface
    wall_features, roof_features, ground_features = [], [], []
    for r in lod2_rows:
        feat = make_feature(r["geom_json"], {"surface_type": r["objectclass_id"]})
        oc = r["objectclass_id"]
        if oc == 33:
            roof_features.append(feat)
        elif oc == 34:
            wall_features.append(feat)
        elif oc == 35:
            ground_features.append(feat)

    def fc(features):
        return {"type": "FeatureCollection", "features": features}

    def _generic_value(r):
        dt = r["datatype"]
        if dt == 1:
            return r["strval"]
        elif dt == 2:
            return r["intval"]
        elif dt in (3, 6):
            v = r["realval"]
            return round(float(v), 3) if v is not None else None
        else:
            return r["strval"]

    return {
        "gmlid": attr["gmlid"],
        "attributes": {
            "name": attr["name"] or None,
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
            "class_label": CLASS_LABELS.get(attr["class"] or "", ""),
            "has_lod2": bool(attr["has_lod2"]),
        },
        "generic_attrs": [
            {"name": r["attrname"], "value": _generic_value(r)}
            for r in generic_rows
        ],
        "lod1": lod1_fc,
        "lod2": {
            "wall": fc(wall_features),
            "roof": fc(roof_features),
            "ground": fc(ground_features),
        },
    }
