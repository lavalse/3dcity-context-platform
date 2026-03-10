"""
Features API — attribute lookup and editing for non-building city objects.

GET  /api/features/{gmlid}   — Returns feature_type + attributes + lod1 geometry
PATCH /api/features/{gmlid}  — Update name/class/function/usage

Buildings are handled by /api/buildings/{gmlid} instead.
"""

import json

from fastapi import APIRouter, HTTPException, Request

from app.database import get_pool
from app.services.versioning import archive_and_next_version, insert_version

router = APIRouter()

# Maps objectclass.classname → type-specific attribute query (returns name + type attrs)
CLASSNAME_QUERIES = {
    'LandUse':   "SELECT lu.class, lu.function, lu.usage FROM citydb.land_use lu WHERE lu.id = $1",
    'Road':      "SELECT tc.class, tc.function, tc.usage FROM citydb.transportation_complex tc WHERE tc.id = $1",
    'WaterBody': "SELECT wb.class, wb.function, wb.usage FROM citydb.waterbody wb WHERE wb.id = $1",
    'Bridge':    "SELECT br.class, br.function, br.usage FROM citydb.bridge br WHERE br.id = $1",
    'CityFurniture':    "SELECT cf.class, cf.function, cf.usage FROM citydb.city_furniture cf WHERE cf.id = $1",
    'PlantCover':       "SELECT pc.class, pc.function, pc.usage FROM citydb.plant_cover pc WHERE pc.id = $1",
    'SolitaryVegetationObject': None,  # no class/function/usage columns
}

# Maps classname → LOD1 footprint + height query
LOD1_QUERIES = {
    'Bridge': """
        SELECT ST_AsGeoJSON(ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),15,0) AS footprint,
               GREATEST(ST_ZMax(ST_Union(sg.geometry)) - ST_ZMin(ST_Union(sg.geometry)), 1.0) AS height
        FROM citydb.bridge br
        JOIN citydb.surface_geometry sg ON sg.root_id = br.lod1_solid_id
        WHERE br.id = $1 AND sg.geometry IS NOT NULL""",
    'CityFurniture': """
        SELECT ST_AsGeoJSON(ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),15,0) AS footprint,
               GREATEST(ST_ZMax(ST_Union(sg.geometry)) - ST_ZMin(ST_Union(sg.geometry)), 1.0) AS height
        FROM citydb.city_furniture cf
        JOIN citydb.surface_geometry sg ON sg.root_id = cf.lod1_brep_id
        WHERE cf.id = $1 AND cf.lod1_brep_id IS NOT NULL AND sg.geometry IS NOT NULL""",
    'PlantCover': """
        SELECT ST_AsGeoJSON(ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),15,0) AS footprint,
               GREATEST(ST_ZMax(ST_Union(sg.geometry)) - ST_ZMin(ST_Union(sg.geometry)), 1.0) AS height
        FROM citydb.plant_cover pc
        JOIN citydb.surface_geometry sg ON sg.root_id = pc.lod1_multi_solid_id
        WHERE pc.id = $1 AND pc.lod1_multi_solid_id IS NOT NULL AND sg.geometry IS NOT NULL""",
    'SolitaryVegetationObject': """
        SELECT ST_AsGeoJSON(ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),15,0) AS footprint,
               GREATEST(ST_ZMax(ST_Union(sg.geometry)) - ST_ZMin(ST_Union(sg.geometry)), 1.0) AS height
        FROM citydb.solitary_vegetat_object sv
        JOIN citydb.surface_geometry sg ON sg.root_id = sv.lod1_brep_id
        WHERE sv.id = $1 AND sv.lod1_brep_id IS NOT NULL AND sg.geometry IS NOT NULL""",
}

# Tables that support class/function/usage edits
CLASSNAME_TO_TABLE = {
    'Bridge':        'citydb.bridge',
    'CityFurniture': 'citydb.city_furniture',
    'PlantCover':    'citydb.plant_cover',
}


async def _get_feature_data(conn, gmlid: str) -> dict:
    """Core fetch logic shared by GET and PATCH handlers."""
    row = await conn.fetchrow(
        "SELECT co.id, co.name, oc.classname "
        "FROM citydb.cityobject co "
        "JOIN citydb.objectclass oc ON oc.id = co.objectclass_id "
        "WHERE co.gmlid = $1",
        gmlid,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Feature not found: {gmlid}")

    classname = row["classname"]
    if classname not in CLASSNAME_QUERIES:
        raise HTTPException(
            status_code=422,
            detail=f"Feature type '{classname}' not supported here",
        )

    query = CLASSNAME_QUERIES[classname]
    attrs = dict(await conn.fetchrow(query, row["id"])) if query else {}
    attrs["name"] = row["name"]

    # LOD1 geometry
    lod1 = None
    lod1_query = LOD1_QUERIES.get(classname)
    if lod1_query:
        lod1_row = await conn.fetchrow(lod1_query, row["id"])
        if lod1_row and lod1_row["footprint"]:
            lod1 = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": json.loads(lod1_row["footprint"]),
                    "properties": {"height": float(lod1_row["height"])},
                }],
            }

    return {
        "gmlid": gmlid,
        "feature_type": classname,
        "attributes": attrs,
        "lod1": lod1,
    }


@router.get("/features/{gmlid}")
async def get_feature(gmlid: str):
    """Return feature_type, attributes, and optional LOD1 geometry."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            return await _get_feature_data(conn, gmlid)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/features/{gmlid}")
async def patch_feature(gmlid: str, request: Request):
    """Update name, class, function, usage for bridge/furniture/vegetation features."""
    body = await request.json()
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            # Look up feature
            row = await conn.fetchrow(
                "SELECT co.id, oc.classname "
                "FROM citydb.cityobject co "
                "JOIN citydb.objectclass oc ON oc.id = co.objectclass_id "
                "WHERE co.gmlid = $1",
                gmlid,
            )
            if not row:
                raise HTTPException(status_code=404, detail=f"Feature not found: {gmlid}")

            classname = row["classname"]
            feature_id = row["id"]

            if classname not in CLASSNAME_QUERIES:
                raise HTTPException(status_code=422, detail=f"Feature type '{classname}' not editable here")

            async with conn.transaction():
                # Version: archive current before update
                next_ver = await archive_and_next_version(conn, gmlid)

                # Update cityobject.name if provided
                if "name" in body:
                    await conn.execute(
                        "UPDATE citydb.cityobject SET name=$1 WHERE gmlid=$2",
                        body["name"] or None, gmlid,
                    )

                # Update type-specific table for class/function/usage
                table = CLASSNAME_TO_TABLE.get(classname)
                if table:
                    updates = {}
                    if "class" in body:
                        updates["class"] = body["class"]
                    if "function" in body:
                        updates["function"] = body["function"]
                    if "usage" in body:
                        updates["usage"] = body["usage"]
                    if updates:
                        set_clauses = ", ".join(
                            f'"{col}" = ${i+2}' for i, col in enumerate(updates.keys())
                        )
                        values = list(updates.values()) + [feature_id]
                        await conn.execute(
                            f"UPDATE {table} SET {set_clauses} WHERE id = ${len(values)}",
                            *values,
                        )

                # Read updated attrs for snapshot
                name_row = await conn.fetchrow(
                    "SELECT name FROM citydb.cityobject WHERE gmlid = $1", gmlid
                )
                attr_snapshot: dict = {"name": name_row["name"]}
                q = CLASSNAME_QUERIES.get(classname)
                if q:
                    attr_row = await conn.fetchrow(q, feature_id)
                    attr_snapshot.update(dict(attr_row))
                await insert_version(conn, gmlid, next_ver, "attr_update", attr_snapshot)

            return await _get_feature_data(conn, gmlid)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
