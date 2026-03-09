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
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi import Query as QueryParam
from fastapi.responses import Response
from pydantic import BaseModel

from app.database import get_pool

router = APIRouter()


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)

# --- Shared SQL for export endpoints ---
_EXPORT_ATTR_SQL = """
    SELECT
        co.gmlid,
        b.measured_height,
        b.usage,
        b.class,
        b.storeys_above_ground,
        (b.lod2_solid_id IS NOT NULL) AS has_lod2
    FROM citydb.building b
    JOIN citydb.cityobject co ON co.id = b.id
    WHERE co.gmlid = $1 AND b.building_root_id = b.id
    LIMIT 1
"""

# LOD2 surfaces with Z coordinates (no ST_Force2D)
_LOD2_3D_SQL = """
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

# LOD2 surfaces projected to EPSG:6677 (JGD2011 Japan Plane Rectangular CS IX, meters)
# Used for CityJSON export — CityJSON requires a projected metric CRS.
# ST_FlipCoordinates + ST_SetSRID(4326) is required because PostGIS/PROJ fails to
# transform directly from EPSG:6668 (axis-order issue in stored SRID definition).
# JGD2011 and WGS84 are practically identical for this purpose (<1m difference).
_LOD2_3D_PROJECTED_SQL = """
    SELECT
        ts.objectclass_id,
        ST_AsGeoJSON(ST_Transform(ST_SetSRID(ST_FlipCoordinates(sg.geometry), 4326), 6677), 6, 0) AS geom_json
    FROM citydb.building b
    JOIN citydb.cityobject co ON co.id = b.id
    JOIN citydb.thematic_surface ts ON ts.building_id = b.id
    JOIN citydb.surface_geometry sg ON sg.root_id = ts.lod2_multi_surface_id
    WHERE co.gmlid = $1
      AND sg.geometry IS NOT NULL
"""

_SURFACE_PROP = {33: "roof", 34: "wall", 35: "ground"}
_CITYJSON_TYPE = {33: "RoofSurface", 34: "WallSurface", 35: "GroundSurface"}

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


@router.get("/buildings/search")
async def search_buildings_by_bbox(
    bbox: str = QueryParam(..., description="lon_min,lat_min,lon_max,lat_max")
):
    """Return gmlids of buildings whose footprint intersects the given bbox."""
    try:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError
        lon_min, lat_min, lon_max, lat_max = parts
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox must be lon_min,lat_min,lon_max,lat_max")

    if (lon_max - lon_min) > 1.0 or (lat_max - lat_min) > 1.0:
        raise HTTPException(status_code=400, detail="bbox too large (max 1° per side)")

    sql = """
        SELECT gmlid FROM citydb.building_footprints
        WHERE ST_Intersects(geometry, ST_MakeEnvelope($1, $2, $3, $4, 4326))
        LIMIT 500
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, lon_min, lat_min, lon_max, lat_max)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"gmlids": [r["gmlid"] for r in rows], "count": len(rows)}


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


@router.get("/buildings/{gmlid}/export/geojson3d")
async def export_building_lod2_geojson(gmlid: str):
    """Return LOD2 3D surfaces as GeoJSON FeatureCollection (with Z coordinates) for download."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            attr_rows = await conn.fetch(_EXPORT_ATTR_SQL, gmlid)
            lod2_rows = await conn.fetch(_LOD2_3D_SQL, gmlid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not attr_rows:
        raise HTTPException(status_code=404, detail=f"Building not found: {gmlid}")

    attr = attr_rows[0]
    height = (
        float(attr["measured_height"])
        if attr["measured_height"] and float(attr["measured_height"]) > 0
        else None
    )

    features = []
    for row in lod2_rows:
        geom = json.loads(row["geom_json"])
        oc = row["objectclass_id"]
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "gmlid": attr["gmlid"],
                "surface_type": _SURFACE_PROP.get(oc, "unknown"),
                "measured_height": height,
                "usage": attr["usage"],
            },
        })

    fc = {"type": "FeatureCollection", "features": features}
    filename = f"{gmlid}_lod2_3d.geojson"
    return Response(
        content=json.dumps(fc, ensure_ascii=False),
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/buildings/{gmlid}/export/cityjson")
async def export_building_cityjson(gmlid: str):
    """Return LOD2 3D surfaces as CityJSON 1.1 for download."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            attr_rows = await conn.fetch(_EXPORT_ATTR_SQL, gmlid)
            lod2_rows = await conn.fetch(_LOD2_3D_PROJECTED_SQL, gmlid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not attr_rows:
        raise HTTPException(status_code=404, detail=f"Building not found: {gmlid}")

    attr = attr_rows[0]
    height = (
        float(attr["measured_height"])
        if attr["measured_height"] and float(attr["measured_height"]) > 0
        else None
    )
    storeys = (
        attr["storeys_above_ground"]
        if attr["storeys_above_ground"] and attr["storeys_above_ground"] != 9999
        else None
    )

    # Build CityJSON vertex list + Solid boundary references
    vertices: list[list[float]] = []
    vertex_map: dict[tuple, int] = {}
    shell: list = []        # list of faces (each face = list of rings)
    semantic_surfaces: list[dict] = []
    semantic_values: list[int] = []

    def get_vertex_idx(coord: list) -> int:
        key = tuple(round(c, 10) for c in coord)
        if key not in vertex_map:
            vertex_map[key] = len(vertices)
            vertices.append(list(key))
        return vertex_map[key]

    for row in lod2_rows:
        geom = json.loads(row["geom_json"])
        oc = row["objectclass_id"]
        sem_idx = len(semantic_surfaces)
        semantic_surfaces.append({"type": _CITYJSON_TYPE.get(oc, "WallSurface")})

        polygons = (
            [geom["coordinates"]] if geom["type"] == "Polygon"
            else geom["coordinates"] if geom["type"] == "MultiPolygon"
            else []
        )
        for poly_coords in polygons:
            face = [[get_vertex_idx(v) for v in ring] for ring in poly_coords]
            shell.append(face)
            semantic_values.append(sem_idx)

    # CityJSON Solid: boundaries = [shell], semantics.values = [shell_values]
    geometry = []
    if shell:
        geometry = [{
            "type": "Solid",
            "lod": "2",
            "boundaries": [shell],
            "semantics": {
                "surfaces": semantic_surfaces,
                "values": [semantic_values],
            },
        }]

    building_attrs = {"gmlid": attr["gmlid"]}
    if height is not None:
        building_attrs["measuredHeight"] = height
    if attr["usage"]:
        building_attrs["usage"] = attr["usage"]
        building_attrs["usageLabel"] = USAGE_LABELS.get(attr["usage"], "不明")
    if storeys is not None:
        building_attrs["storeysAboveGround"] = storeys

    cityjson = {
        "type": "CityJSON",
        "version": "1.1",
        "transform": {"scale": [1.0, 1.0, 1.0], "translate": [0.0, 0.0, 0.0]},
        "metadata": {
            "referenceSystem": "urn:ogc:def:crs:EPSG::6677"
        },
        "vertices": vertices,
        "CityObjects": {
            gmlid: {
                "type": "Building",
                "attributes": building_attrs,
                "geometry": geometry,
            }
        },
    }

    filename = f"{gmlid}.city.json"
    return Response(
        content=json.dumps(cityjson, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Batch export ──

class BatchExportRequest(BaseModel):
    gmlids: list[str]
    format: Literal["geojson3d", "cityjson"]


@router.post("/buildings/export/batch")
async def export_buildings_batch(body: BatchExportRequest):
    """Export multiple buildings as GeoJSON 3D or CityJSON."""
    if not body.gmlids:
        raise HTTPException(status_code=400, detail="No gmlids provided")
    if len(body.gmlids) > 500:
        raise HTTPException(status_code=400, detail="Too many buildings (max 500)")
    gmlids = list(dict.fromkeys(body.gmlids))  # deduplicate, preserve order

    attr_sql = """
        SELECT co.gmlid, b.measured_height, b.usage, b.class,
               b.storeys_above_ground, (b.lod2_solid_id IS NOT NULL) AS has_lod2
        FROM citydb.building b
        JOIN citydb.cityobject co ON co.id = b.id
        WHERE co.gmlid = ANY($1) AND b.building_root_id = b.id
    """
    # GeoJSON 3D uses lon/lat; CityJSON uses projected metric CRS (EPSG:6677)
    if body.format == "cityjson":
        lod2_sql = """
            SELECT co.gmlid, ts.objectclass_id,
                   ST_AsGeoJSON(ST_Transform(ST_SetSRID(ST_FlipCoordinates(sg.geometry), 4326), 6677), 6, 0) AS geom_json
            FROM citydb.building b
            JOIN citydb.cityobject co ON co.id = b.id
            JOIN citydb.thematic_surface ts ON ts.building_id = b.id
            JOIN citydb.surface_geometry sg ON sg.root_id = ts.lod2_multi_surface_id
            WHERE co.gmlid = ANY($1) AND sg.geometry IS NOT NULL
        """
    else:
        lod2_sql = """
            SELECT co.gmlid, ts.objectclass_id,
                   ST_AsGeoJSON(ST_FlipCoordinates(sg.geometry), 15, 0) AS geom_json
            FROM citydb.building b
            JOIN citydb.cityobject co ON co.id = b.id
            JOIN citydb.thematic_surface ts ON ts.building_id = b.id
            JOIN citydb.surface_geometry sg ON sg.root_id = ts.lod2_multi_surface_id
            WHERE co.gmlid = ANY($1) AND sg.geometry IS NOT NULL
        """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            attr_rows = await conn.fetch(attr_sql, gmlids)
            lod2_rows = await conn.fetch(lod2_sql, gmlids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    attrs = {r["gmlid"]: r for r in attr_rows}
    surfaces_by_gmlid: dict[str, list] = {}
    for r in lod2_rows:
        surfaces_by_gmlid.setdefault(r["gmlid"], []).append(r)

    if body.format == "geojson3d":
        return _build_batch_geojson3d(gmlids, attrs, surfaces_by_gmlid)
    return _build_batch_cityjson(gmlids, attrs, surfaces_by_gmlid)


def _build_batch_geojson3d(gmlids, attrs, surfaces_by_gmlid):
    features = []
    for gmlid in gmlids:
        attr = attrs.get(gmlid)
        surfaces = surfaces_by_gmlid.get(gmlid, [])
        height = None
        usage = None
        if attr:
            height = (
                float(attr["measured_height"])
                if attr["measured_height"] and float(attr["measured_height"]) > 0
                else None
            )
            usage = attr["usage"]
        for row in surfaces:
            geom = json.loads(row["geom_json"])
            oc = row["objectclass_id"]
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "gmlid": gmlid,
                    "surface_type": _SURFACE_PROP.get(oc, "unknown"),
                    "measured_height": height,
                    "usage": usage,
                },
            })
    fc = {"type": "FeatureCollection", "features": features}
    return Response(
        content=json.dumps(fc, ensure_ascii=False, cls=_DecimalEncoder),
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="batch_{len(gmlids)}bldg.geojson"'},
    )


def _build_batch_cityjson(gmlids, attrs, surfaces_by_gmlid):
    vertices: list[list[float]] = []
    vertex_map: dict[tuple, int] = {}
    city_objects: dict = {}

    def get_vertex_idx(coord: list) -> int:
        key = tuple(round(c, 10) for c in coord)
        if key not in vertex_map:
            vertex_map[key] = len(vertices)
            vertices.append(list(key))
        return vertex_map[key]

    for gmlid in gmlids:
        attr = attrs.get(gmlid)
        surfaces = surfaces_by_gmlid.get(gmlid, [])

        shell: list = []
        semantic_surfaces: list[dict] = []
        semantic_values: list[int] = []

        for row in surfaces:
            geom = json.loads(row["geom_json"])
            oc = row["objectclass_id"]
            sem_idx = len(semantic_surfaces)
            semantic_surfaces.append({"type": _CITYJSON_TYPE.get(oc, "WallSurface")})
            polygons = (
                [geom["coordinates"]] if geom["type"] == "Polygon"
                else geom["coordinates"] if geom["type"] == "MultiPolygon"
                else []
            )
            for poly_coords in polygons:
                face = [[get_vertex_idx(v) for v in ring] for ring in poly_coords]
                shell.append(face)
                semantic_values.append(sem_idx)

        geometry = []
        if shell:
            geometry = [{
                "type": "Solid",
                "lod": "2",
                "boundaries": [shell],
                "semantics": {
                    "surfaces": semantic_surfaces,
                    "values": [semantic_values],
                },
            }]

        building_attrs = {"gmlid": gmlid}
        if attr:
            height = (
                float(attr["measured_height"])
                if attr["measured_height"] and float(attr["measured_height"]) > 0
                else None
            )
            storeys = (
                attr["storeys_above_ground"]
                if attr["storeys_above_ground"] and attr["storeys_above_ground"] != 9999
                else None
            )
            if height is not None:
                building_attrs["measuredHeight"] = height
            if attr["usage"]:
                building_attrs["usage"] = attr["usage"]
                building_attrs["usageLabel"] = USAGE_LABELS.get(attr["usage"], "不明")
            if storeys is not None:
                building_attrs["storeysAboveGround"] = storeys

        city_objects[gmlid] = {
            "type": "Building",
            "attributes": building_attrs,
            "geometry": geometry,
        }

    cityjson = {
        "type": "CityJSON",
        "version": "1.1",
        "transform": {"scale": [1.0, 1.0, 1.0], "translate": [0.0, 0.0, 0.0]},
        "metadata": {
            "referenceSystem": "urn:ogc:def:crs:EPSG::6677"
        },
        "vertices": vertices,
        "CityObjects": city_objects,
    }
    return Response(
        content=json.dumps(cityjson, ensure_ascii=False, cls=_DecimalEncoder),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="batch_{len(gmlids)}bldg.city.json"'},
    )
