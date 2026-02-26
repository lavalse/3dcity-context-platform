-- 001_building_footprints_mv.sql
-- Creates a materialized view of building LOD1 footprints (2D convex hull)
-- projected to WGS84 (EPSG:4326) for use with Martin MVT tile server.
--
-- Runtime: ~30–90 seconds for 72,486 buildings.
-- Run with:
--   docker exec -i 3dcitydb-pg psql -U citydb -d citydb \
--     < data/migrations/001_building_footprints_mv.sql

DROP MATERIALIZED VIEW IF EXISTS citydb.building_footprints;

CREATE MATERIALIZED VIEW citydb.building_footprints AS
SELECT
    co.gmlid,
    COALESCE(b.measured_height, 0)       AS measured_height,
    b.usage,
    (b.lod2_solid_id IS NOT NULL)        AS has_lod2,
    ST_SetSRID(
        ST_FlipCoordinates(
            ST_Force2D(
                ST_ConvexHull(ST_Collect(sg.geometry))
            )
        ),
        4326
    )::geometry(Geometry, 4326)          AS geometry
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
JOIN citydb.surface_geometry sg ON sg.root_id = b.lod1_solid_id
WHERE b.building_root_id = b.id
  AND sg.geometry IS NOT NULL
GROUP BY co.gmlid, b.id, b.measured_height, b.usage, b.lod2_solid_id;

-- Spatial index required by Martin and PostGIS bbox queries
CREATE INDEX ON citydb.building_footprints USING GIST(geometry);

-- Verify
SELECT COUNT(*) AS building_count FROM citydb.building_footprints;
