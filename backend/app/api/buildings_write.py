"""
Building CRUD write endpoints.

PATCH  /api/buildings/{gmlid}       — update attributes
DELETE /api/buildings/{gmlid}       — cascade delete building
PUT    /api/buildings/{gmlid}/lod1  — replace LOD1 footprint geometry
PUT    /api/buildings/{gmlid}/lod2  — replace LOD2 thematic surfaces

Read path (GET /api/buildings/{gmlid}) remains in buildings.py, unchanged.
"""

import json
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.database import get_pool
from app.database_write import update_building_footprint, delete_building_footprint
from app.api.buildings import USAGE_LABELS

router = APIRouter()

VALID_USAGE_CODES = set(USAGE_LABELS.keys())


# ── Pydantic models ────────────────────────────────────────────────────────────

class BuildingPatch(BaseModel):
    name: Optional[str] = None
    usage: Optional[str] = None
    measured_height: Optional[float] = None
    storeys_above_ground: Optional[int] = None

    @field_validator("usage")
    @classmethod
    def _validate_usage(cls, v):
        if v is not None and v not in VALID_USAGE_CODES:
            raise ValueError(f"Invalid usage code: {v}. Valid codes: {sorted(VALID_USAGE_CODES)}")
        return v

    @field_validator("measured_height")
    @classmethod
    def _validate_height(cls, v):
        if v is not None and v < 0:
            raise ValueError("measured_height must be >= 0")
        return v

    @field_validator("storeys_above_ground")
    @classmethod
    def _validate_storeys(cls, v):
        if v is not None and v < 1:
            raise ValueError("storeys_above_ground must be >= 1")
        return v


class Lod1Put(BaseModel):
    polygon: dict   # GeoJSON Polygon (WGS84 lon/lat)
    height: float   # building height in metres


class Lod2Surface(BaseModel):
    type: Literal["wall", "roof", "ground"]
    geometry: dict  # GeoJSON Polygon with 3D coordinates


class Lod2Put(BaseModel):
    surfaces: list[Lod2Surface]


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_building_row(gmlid: str):
    """Return the building row (id, lod1_solid_id, lod2_solid_id) for a root building."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT b.id, b.lod1_solid_id, b.lod2_solid_id
            FROM citydb.building b
            JOIN citydb.cityobject co ON co.id = b.id
            WHERE co.gmlid = $1 AND b.building_root_id = b.id
            LIMIT 1
            """,
            gmlid,
        )
    return row


def _build_lod1_faces(coordinates: list, height: float) -> list[str]:
    """
    Compute WKT POLYGON Z strings for LOD1 solid faces (ground, roof, walls).

    coordinates: GeoJSON outer ring as list of [lon, lat] pairs
    height:      building height in metres
    Returns:     WKT strings with lat/lon coordinate order for EPSG:6668 storage
    """
    ring = list(coordinates[0])   # outer ring only
    if ring[0] != ring[-1]:
        ring.append(ring[0])      # close the ring

    def pt(p, z):
        lon, lat = p[0], p[1]
        return f"{lat} {lon} {z}"

    faces = []

    # Ground face (z = 0)
    pts = ", ".join(pt(p, 0) for p in ring)
    faces.append(f"POLYGON Z(({pts}))")

    # Roof face (z = height)
    pts = ", ".join(pt(p, height) for p in ring)
    faces.append(f"POLYGON Z(({pts}))")

    # Wall face for each edge
    n = len(ring) - 1   # number of unique vertices (ring is closed)
    for i in range(n):
        p0, p1 = ring[i], ring[i + 1]
        lon0, lat0 = p0[0], p0[1]
        lon1, lat1 = p1[0], p1[1]
        wall = (
            f"{lat0} {lon0} 0, "
            f"{lat1} {lon1} 0, "
            f"{lat1} {lon1} {height}, "
            f"{lat0} {lon0} {height}, "
            f"{lat0} {lon0} 0"
        )
        faces.append(f"POLYGON Z(({wall}))")

    return faces


def _geojson_polygon_to_wkt_6668(coords: list) -> str:
    """
    Convert GeoJSON polygon coordinates [lon, lat, z] to WKT with EPSG:6668 axis order.
    EPSG:6668 stores coordinates as lat, lon (Y, X).
    """
    rings = []
    for ring in coords:
        pts = []
        for pt in ring:
            lon, lat = pt[0], pt[1]
            z = pt[2] if len(pt) > 2 else 0.0
            pts.append(f"{lat} {lon} {z}")
        rings.append(f"({', '.join(pts)})")
    return f"POLYGON Z({', '.join(rings)})"


# ── PATCH /api/buildings/{gmlid} ──────────────────────────────────────────────

@router.patch("/buildings/{gmlid}")
async def patch_building(gmlid: str, body: BuildingPatch):
    """Update building attributes (name, usage, measured_height, storeys_above_ground)."""
    row = await _get_building_row(gmlid)
    if not row:
        raise HTTPException(status_code=404, detail=f"Building not found: {gmlid}")

    building_id = row["id"]
    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Update cityobject.name if provided
                if body.name is not None:
                    await conn.execute(
                        "UPDATE citydb.cityobject SET name = $1 WHERE id = $2",
                        body.name or None,
                        building_id,
                    )

                # Build dynamic UPDATE for building table
                set_clauses = []
                args = []
                idx = 1

                if body.usage is not None:
                    set_clauses.append(f"usage = ${idx}")
                    args.append(body.usage or None)
                    idx += 1

                if body.measured_height is not None:
                    set_clauses.append(f"measured_height = ${idx}")
                    args.append(body.measured_height)
                    idx += 1
                elif "measured_height" in body.model_fields_set and body.measured_height is None:
                    set_clauses.append(f"measured_height = ${idx}")
                    args.append(-9999.0)
                    idx += 1

                if body.storeys_above_ground is not None:
                    set_clauses.append(f"storeys_above_ground = ${idx}")
                    args.append(body.storeys_above_ground)
                    idx += 1
                elif "storeys_above_ground" in body.model_fields_set and body.storeys_above_ground is None:
                    set_clauses.append(f"storeys_above_ground = ${idx}")
                    args.append(9999)
                    idx += 1

                if set_clauses:
                    args.append(building_id)
                    await conn.execute(
                        f"UPDATE citydb.building SET {', '.join(set_clauses)} WHERE id = ${idx}",
                        *args,
                    )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    await update_building_footprint(gmlid)

    # Return updated record in the same format as GET /api/buildings/{gmlid}
    from app.api.buildings import get_building_detail
    return await get_building_detail(gmlid)


# ── DELETE /api/buildings/{gmlid} ─────────────────────────────────────────────

@router.delete("/buildings/{gmlid}")
async def delete_building(gmlid: str):
    """
    Cascade-delete a building and all its related records.
    Returns {"deleted": gmlid}.
    Triggers async MV refresh.
    """
    row = await _get_building_row(gmlid)
    if not row:
        raise HTTPException(status_code=404, detail=f"Building not found: {gmlid}")

    building_id = row["id"]
    lod1_solid_id = row["lod1_solid_id"]
    lod2_solid_id = row["lod2_solid_id"]

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            # Collect thematic surface IDs
            ts_rows = await conn.fetch(
                "SELECT id, lod2_multi_surface_id FROM citydb.thematic_surface WHERE building_id = $1",
                building_id,
            )
            ts_ids = [r["id"] for r in ts_rows]
            ts_geom_ids = [r["lod2_multi_surface_id"] for r in ts_rows if r["lod2_multi_surface_id"]]

            # Collect all geometry root IDs to delete
            all_geom_root_ids = list({x for x in [lod1_solid_id, lod2_solid_id] + ts_geom_ids if x})

            async with conn.transaction():
                # 1. Break FK: building → surface_geometry (all geometry columns)
                await conn.execute(
                    """
                    UPDATE citydb.building
                    SET lod0_footprint_id = NULL, lod0_roofprint_id = NULL,
                        lod1_solid_id = NULL, lod2_solid_id = NULL,
                        lod3_solid_id = NULL, lod4_solid_id = NULL
                    WHERE id = $1
                    """,
                    building_id,
                )

                # 2. Break FK: thematic_surface → surface_geometry
                if ts_ids:
                    await conn.execute(
                        "UPDATE citydb.thematic_surface "
                        "SET lod2_multi_surface_id = NULL, lod3_multi_surface_id = NULL, lod4_multi_surface_id = NULL "
                        "WHERE building_id = $1",
                        building_id,
                    )

                # 3. Delete surface_geometry (root_id self-references all children)
                if all_geom_root_ids:
                    await conn.execute(
                        "DELETE FROM citydb.surface_geometry WHERE root_id = ANY($1)",
                        all_geom_root_ids,
                    )
                # Also delete any remaining surface_geometry referencing this building directly
                await conn.execute(
                    "DELETE FROM citydb.surface_geometry WHERE cityobject_id = $1",
                    building_id,
                )

                # 4. Delete thematic_surface rows, then their cityobject entries
                await conn.execute(
                    "DELETE FROM citydb.thematic_surface WHERE building_id = $1",
                    building_id,
                )
                if ts_ids:
                    await conn.execute(
                        "DELETE FROM citydb.cityobject WHERE id = ANY($1)",
                        ts_ids,
                    )

                # 5. Delete genericattrib, address links, building, cityobject
                await conn.execute(
                    "DELETE FROM citydb.cityobject_genericattrib WHERE cityobject_id = $1",
                    building_id,
                )
                await conn.execute(
                    "DELETE FROM citydb.address_to_building WHERE building_id = $1",
                    building_id,
                )
                await conn.execute(
                    "DELETE FROM citydb.building WHERE id = $1",
                    building_id,
                )
                await conn.execute(
                    "DELETE FROM citydb.cityobject WHERE id = $1",
                    building_id,
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    await delete_building_footprint(gmlid)
    return {"deleted": gmlid}


# ── PUT /api/buildings/{gmlid}/lod1 ──────────────────────────────────────────

@router.put("/buildings/{gmlid}/lod1")
async def put_building_lod1(gmlid: str, body: Lod1Put):
    """
    Replace the LOD1 footprint solid geometry.
    Accepts a GeoJSON Polygon (WGS84 lon/lat) and building height in metres.
    """
    if body.polygon.get("type") != "Polygon":
        raise HTTPException(status_code=400, detail="polygon must be a GeoJSON Polygon")
    coords = body.polygon.get("coordinates")
    if not coords or len(coords[0]) < 4:
        raise HTTPException(status_code=400, detail="Polygon must have at least 3 vertices")
    if body.height <= 0:
        raise HTTPException(status_code=400, detail="height must be > 0")

    row = await _get_building_row(gmlid)
    if not row:
        raise HTTPException(status_code=404, detail=f"Building not found: {gmlid}")

    building_id = row["id"]
    old_lod1_solid_id = row["lod1_solid_id"]

    face_wkts = _build_lod1_faces(coords, body.height)

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # 1. Break FK from building to old solid
                await conn.execute(
                    "UPDATE citydb.building SET lod1_solid_id = NULL WHERE id = $1",
                    building_id,
                )

                # 2. Delete old surface_geometry
                if old_lod1_solid_id:
                    await conn.execute(
                        "DELETE FROM citydb.surface_geometry WHERE root_id = $1",
                        old_lod1_solid_id,
                    )

                # 3. Insert new root surface_geometry (solid, no geometry in root row)
                new_root_id = await conn.fetchval(
                    """
                    INSERT INTO citydb.surface_geometry
                        (parent_id, root_id, is_solid, is_composite, is_triangulated,
                         is_xlink, is_reverse, cityobject_id)
                    VALUES (NULL, NULL, 1, 0, 0, 0, 0, $1)
                    RETURNING id
                    """,
                    building_id,
                )
                # Self-reference: root_id = id
                await conn.execute(
                    "UPDATE citydb.surface_geometry SET root_id = $1 WHERE id = $1",
                    new_root_id,
                )

                # 4. Insert individual face polygons
                for wkt in face_wkts:
                    await conn.execute(
                        """
                        INSERT INTO citydb.surface_geometry
                            (parent_id, root_id, is_solid, is_composite, is_triangulated,
                             is_xlink, is_reverse, geometry, cityobject_id)
                        VALUES ($1, $2, 0, 0, 0, 0, 0, ST_GeomFromText($3, 6668), $4)
                        """,
                        new_root_id, new_root_id, wkt, building_id,
                    )

                # 5. Update building LOD1 reference and measured_height
                await conn.execute(
                    "UPDATE citydb.building SET lod1_solid_id = $1, measured_height = $2 WHERE id = $3",
                    new_root_id, body.height, building_id,
                )

                # 6. Update cityobject envelope (3D bounding polygon in EPSG:6668)
                await conn.execute(
                    """
                    UPDATE citydb.cityobject
                    SET envelope = (
                        SELECT ST_SetSRID(ST_Force3DZ(ST_Envelope(ST_Collect(sg.geometry))), 6668)
                        FROM citydb.surface_geometry sg
                        WHERE sg.root_id = $1 AND sg.geometry IS NOT NULL
                    )
                    WHERE id = $2
                    """,
                    new_root_id, building_id,
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    await update_building_footprint(gmlid)

    from app.api.buildings import get_building_detail
    return await get_building_detail(gmlid)


# ── PUT /api/buildings/{gmlid}/lod2 ──────────────────────────────────────────

_SURFACE_OC = {"roof": 33, "wall": 34, "ground": 35}


@router.put("/buildings/{gmlid}/lod2")
async def put_building_lod2(gmlid: str, body: Lod2Put):
    """
    Replace LOD2 thematic surfaces.
    Accepts a list of surfaces, each with type ('wall'|'roof'|'ground')
    and a GeoJSON Polygon with 3D coordinates (lon, lat, z WGS84).
    """
    if not body.surfaces:
        raise HTTPException(status_code=400, detail="surfaces list must not be empty")

    row = await _get_building_row(gmlid)
    if not row:
        raise HTTPException(status_code=404, detail=f"Building not found: {gmlid}")

    building_id = row["id"]
    old_lod2_solid_id = row["lod2_solid_id"]

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            # Collect old thematic surface IDs and their geometry roots
            ts_rows = await conn.fetch(
                "SELECT id, lod2_multi_surface_id FROM citydb.thematic_surface WHERE building_id = $1",
                building_id,
            )
            old_ts_ids = [r["id"] for r in ts_rows]
            old_ms_ids = [r["lod2_multi_surface_id"] for r in ts_rows if r["lod2_multi_surface_id"]]
            if old_lod2_solid_id:
                old_ms_ids.append(old_lod2_solid_id)
            old_ms_ids = list(set(old_ms_ids))

            async with conn.transaction():
                # 1. Break FK: building → lod2_solid_id
                await conn.execute(
                    "UPDATE citydb.building SET lod2_solid_id = NULL WHERE id = $1",
                    building_id,
                )

                # 2. Break FK: thematic_surface → surface_geometry
                if old_ts_ids:
                    await conn.execute(
                        "UPDATE citydb.thematic_surface "
                        "SET lod2_multi_surface_id = NULL WHERE building_id = $1",
                        building_id,
                    )

                # 3. Delete old surface_geometry
                if old_ms_ids:
                    await conn.execute(
                        "DELETE FROM citydb.surface_geometry WHERE root_id = ANY($1)",
                        old_ms_ids,
                    )

                # 4. Delete old thematic_surface rows and their cityobject entries
                await conn.execute(
                    "DELETE FROM citydb.thematic_surface WHERE building_id = $1",
                    building_id,
                )
                if old_ts_ids:
                    await conn.execute(
                        "DELETE FROM citydb.cityobject WHERE id = ANY($1)",
                        old_ts_ids,
                    )

                # 5. Insert new surfaces
                for surface in body.surfaces:
                    oc_id = _SURFACE_OC[surface.type]

                    # 5a. Insert cityobject for this thematic surface
                    ts_gmlid = f"TS-{gmlid}-{uuid.uuid4().hex[:8]}"
                    ts_co_id = await conn.fetchval(
                        "INSERT INTO citydb.cityobject (objectclass_id, gmlid) VALUES ($1, $2) RETURNING id",
                        oc_id, ts_gmlid,
                    )

                    # 5b. Insert surface_geometry root (MultiSurface: is_composite=1)
                    sg_root_id = await conn.fetchval(
                        """
                        INSERT INTO citydb.surface_geometry
                            (parent_id, root_id, is_solid, is_composite, is_triangulated,
                             is_xlink, is_reverse, cityobject_id)
                        VALUES (NULL, NULL, 0, 1, 0, 0, 0, $1)
                        RETURNING id
                        """,
                        ts_co_id,
                    )
                    await conn.execute(
                        "UPDATE citydb.surface_geometry SET root_id = $1 WHERE id = $1",
                        sg_root_id,
                    )

                    # 5c. Insert face polygons
                    coords = surface.geometry.get("coordinates", [])
                    wkt = _geojson_polygon_to_wkt_6668(coords)
                    await conn.execute(
                        """
                        INSERT INTO citydb.surface_geometry
                            (parent_id, root_id, is_solid, is_composite, is_triangulated,
                             is_xlink, is_reverse, geometry, cityobject_id)
                        VALUES ($1, $2, 0, 0, 0, 0, 0, ST_GeomFromText($3, 6668), $4)
                        """,
                        sg_root_id, sg_root_id, wkt, ts_co_id,
                    )

                    # 5d. Insert thematic_surface
                    await conn.execute(
                        """
                        INSERT INTO citydb.thematic_surface
                            (id, objectclass_id, building_id, lod2_multi_surface_id)
                        VALUES ($1, $2, $3, $4)
                        """,
                        ts_co_id, oc_id, building_id, sg_root_id,
                    )

                # 6. Mark building as having LOD2 (use last sg_root_id as lod2_solid_id)
                await conn.execute(
                    "UPDATE citydb.building SET lod2_solid_id = $1 WHERE id = $2",
                    sg_root_id, building_id,
                )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    await update_building_footprint(gmlid)

    from app.api.buildings import get_building_detail
    return await get_building_detail(gmlid)
