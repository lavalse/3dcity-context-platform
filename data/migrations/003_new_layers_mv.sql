-- 003_new_layers_mv.sql
-- Creates materialized views for bridges, city furniture, and vegetation footprints,
-- and refreshes flood_zone_footprints to include htd (high-tide) data.
--
-- Run with:
--   docker exec -i 3dcitydb-pg psql -U citydb -d citydb \
--     < data/migrations/003_new_layers_mv.sql
--
-- Expected counts: bridge_footprints ~59, furniture_footprints ~7053,
--                  vegetation_footprints ~619, flood_zone_footprints ~8761


-- ── Bridges ───────────────────────────────────────────────────────────────────
-- All 59 bridges have lod1_solid_id populated; use bridge_root_id = id to get
-- only top-level Bridge objects (excludes BridgePart children).

DROP MATERIALIZED VIEW IF EXISTS citydb.bridge_footprints;

CREATE MATERIALIZED VIEW citydb.bridge_footprints AS
SELECT
    co.gmlid,
    br.class,
    br.function,
    br.usage,
    ST_SetSRID(
        ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),
        4326
    )::geometry(Geometry, 4326) AS geometry
FROM citydb.bridge br
JOIN citydb.cityobject co ON co.id = br.id
JOIN citydb.surface_geometry sg ON sg.root_id = br.lod1_solid_id
WHERE br.bridge_root_id = br.id
  AND sg.geometry IS NOT NULL
GROUP BY co.gmlid, br.id, br.class, br.function, br.usage;

CREATE INDEX ON citydb.bridge_footprints USING GIST(geometry);

-- Verify
SELECT COUNT(*) AS bridge_count FROM citydb.bridge_footprints;


-- ── City Furniture ────────────────────────────────────────────────────────────
-- 7,053 of 7,193 city_furniture rows have lod1_brep_id populated.

DROP MATERIALIZED VIEW IF EXISTS citydb.furniture_footprints;

CREATE MATERIALIZED VIEW citydb.furniture_footprints AS
SELECT
    co.gmlid,
    cf.class,
    cf.function,
    cf.usage,
    ST_SetSRID(
        ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),
        4326
    )::geometry(Geometry, 4326) AS geometry
FROM citydb.city_furniture cf
JOIN citydb.cityobject co ON co.id = cf.id
JOIN citydb.surface_geometry sg ON sg.root_id = cf.lod1_brep_id
WHERE cf.lod1_brep_id IS NOT NULL
  AND sg.geometry IS NOT NULL
GROUP BY co.gmlid, cf.id, cf.class, cf.function, cf.usage;

CREATE INDEX ON citydb.furniture_footprints USING GIST(geometry);

-- Verify
SELECT COUNT(*) AS furniture_count FROM citydb.furniture_footprints;


-- ── Vegetation ────────────────────────────────────────────────────────────────
-- Combines PlantCover (238 rows, lod1_multi_solid_id) and
-- SolitaryVegetationObject (381 rows with lod1_brep_id).

DROP MATERIALIZED VIEW IF EXISTS citydb.vegetation_footprints;

CREATE MATERIALIZED VIEW citydb.vegetation_footprints AS
-- PlantCover
SELECT
    co.gmlid,
    pc.class,
    pc.usage,
    ST_SetSRID(
        ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),
        4326
    )::geometry(Geometry, 4326) AS geometry
FROM citydb.plant_cover pc
JOIN citydb.cityobject co ON co.id = pc.id
JOIN citydb.surface_geometry sg ON sg.root_id = pc.lod1_multi_solid_id
WHERE pc.lod1_multi_solid_id IS NOT NULL
  AND sg.geometry IS NOT NULL
GROUP BY co.gmlid, pc.id, pc.class, pc.usage

UNION ALL

-- SolitaryVegetationObject
SELECT
    co.gmlid,
    NULL::character varying AS class,
    NULL::character varying AS usage,
    ST_SetSRID(
        ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),
        4326
    )::geometry(Geometry, 4326) AS geometry
FROM citydb.solitary_vegetat_object sv
JOIN citydb.cityobject co ON co.id = sv.id
JOIN citydb.surface_geometry sg ON sg.root_id = sv.lod1_brep_id
WHERE sv.lod1_brep_id IS NOT NULL
  AND sg.geometry IS NOT NULL
GROUP BY co.gmlid, sv.id;

CREATE INDEX ON citydb.vegetation_footprints USING GIST(geometry);

-- Verify
SELECT COUNT(*) AS vegetation_count FROM citydb.vegetation_footprints;


-- ── Refresh flood_zone_footprints to include htd (high-tide) data ─────────────
-- The 002 migration created this view with only fld data (1,740 objects).
-- After importing htd (7,021 objects), a REFRESH picks them up automatically
-- since htd WaterBody rows share the same table (citydb.waterbody).

REFRESH MATERIALIZED VIEW citydb.flood_zone_footprints;

SELECT COUNT(*) AS flood_zone_count FROM citydb.flood_zone_footprints;
