-- Migration 002: Convert building_footprints from Materialized View to regular TABLE
-- This enables instant single-row updates after LOD1/LOD2 edits,
-- instead of requiring a full ~30-90s REFRESH MATERIALIZED VIEW.

DROP MATERIALIZED VIEW IF EXISTS citydb.building_footprints;

CREATE TABLE citydb.building_footprints AS
SELECT
    co.gmlid,
    COALESCE(b.measured_height, 0)       AS measured_height,
    b.usage,
    (b.lod2_solid_id IS NOT NULL)        AS has_lod2,
    ST_SetSRID(
        ST_FlipCoordinates(
            ST_Union(ST_Force2D(sg.geometry))
        ),
        4326
    )::geometry(Geometry, 4326)          AS geometry
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
JOIN citydb.surface_geometry sg ON sg.root_id = b.lod1_solid_id
WHERE b.building_root_id = b.id
  AND sg.geometry IS NOT NULL
GROUP BY co.gmlid, b.id, b.measured_height, b.usage, b.lod2_solid_id;

CREATE UNIQUE INDEX ON citydb.building_footprints (gmlid);
CREATE INDEX ON citydb.building_footprints USING GIST(geometry);

SELECT COUNT(*) AS building_count FROM citydb.building_footprints;
