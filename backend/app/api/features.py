"""
Features API — attribute lookup for non-building city objects.

GET /api/features/{gmlid}
    Returns feature_type + attributes for LandUse, Road, or WaterBody features.
    Buildings are handled by /api/buildings/{gmlid} instead.
"""

from fastapi import APIRouter, HTTPException

from app.database import get_pool

router = APIRouter()

# Maps objectclass.classname → type-specific attribute query.
# Uses classname string match (not hardcoded IDs) per plan guidance.
CLASSNAME_QUERIES = {
    'LandUse': "SELECT lu.class, lu.function, lu.usage FROM citydb.land_use lu WHERE lu.id = $1",
    'Road': "SELECT tc.class, tc.function, tc.usage FROM citydb.transportation_complex tc WHERE tc.id = $1",
    'WaterBody': "SELECT wb.class, wb.function, wb.usage FROM citydb.waterbody wb WHERE wb.id = $1",
}


@router.get("/features/{gmlid}")
async def get_feature(gmlid: str):
    """Return feature_type and attributes for a single non-building city object."""
    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
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
            if classname not in CLASSNAME_QUERIES:
                raise HTTPException(
                    status_code=422,
                    detail=f"Feature type '{classname}' not supported here",
                )

            attrs = await conn.fetchrow(CLASSNAME_QUERIES[classname], row["id"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "gmlid": gmlid,
        "feature_type": classname,
        "attributes": dict(attrs) if attrs else {},
    }
