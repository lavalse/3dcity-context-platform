"""
Write utilities for the 3DCityDB.

Separated from database.py to keep the read path clearly SELECT-only.
run_query() in database.py remains unchanged and still rejects non-SELECT.
"""
from app.database import get_pool


async def execute_write(sql: str, *args) -> None:
    """Execute a single parameterized DML statement."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(sql, *args)


async def execute_transaction(ops: list[tuple[str, list]]) -> None:
    """Execute multiple DML statements atomically."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for sql, args in ops:
                await conn.execute(sql, *args)


async def update_building_footprint(gmlid: str) -> None:
    """Recompute and update the single row for this building in the footprints table."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE citydb.building_footprints fp
            SET geometry         = sub.geometry,
                has_lod2         = sub.has_lod2,
                measured_height  = sub.measured_height,
                usage            = sub.usage
            FROM (
                SELECT
                    co.gmlid,
                    COALESCE(b.measured_height, 0)          AS measured_height,
                    b.usage,
                    (b.lod2_solid_id IS NOT NULL)           AS has_lod2,
                    ST_SetSRID(
                        ST_FlipCoordinates(
                            ST_Union(ST_Force2D(sg.geometry))
                        ), 4326
                    )::geometry(Geometry, 4326)             AS geometry
                FROM citydb.building b
                JOIN citydb.cityobject co ON co.id = b.id
                JOIN citydb.surface_geometry sg
                     ON sg.root_id = b.lod1_solid_id
                WHERE b.building_root_id = b.id
                  AND sg.geometry IS NOT NULL
                  AND co.gmlid = $1
                GROUP BY co.gmlid, b.id,
                         b.measured_height, b.usage, b.lod2_solid_id
            ) sub
            WHERE fp.gmlid = sub.gmlid
            """,
            gmlid,
        )


async def delete_building_footprint(gmlid: str) -> None:
    """Remove the footprint row for a deleted building."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM citydb.building_footprints WHERE gmlid = $1",
            gmlid,
        )
