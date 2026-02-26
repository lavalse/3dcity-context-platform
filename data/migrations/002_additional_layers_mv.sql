-- 002_additional_layers_mv.sql
-- Creates materialized views for land use, road, and flood zone (waterbody) footprints
-- projected to WGS84 (EPSG:4326) for use with Martin MVT tile server.
--
-- Run with:
--   docker exec -i 3dcitydb-pg psql -U citydb -d citydb \
--     < data/migrations/002_additional_layers_mv.sql
--
-- Note: Roads use objectclass_id=45 (Road), not 43 (TransportationComplex base).
--       WaterBody uses lod1_multi_surface_id (lod0 is unpopulated in Taito-ku data).

-- ── Land Use ──────────────────────────────────────────────────────────────────

DROP MATERIALIZED VIEW IF EXISTS citydb.land_use_footprints;

CREATE MATERIALIZED VIEW citydb.land_use_footprints AS
SELECT
    co.gmlid,
    lu.class,
    lu.usage,
    ST_SetSRID(
        ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),
        4326
    )::geometry(Geometry, 4326) AS geometry
FROM citydb.land_use lu
JOIN citydb.cityobject co ON co.id = lu.id
JOIN citydb.surface_geometry sg ON sg.root_id = lu.lod1_multi_surface_id
WHERE sg.geometry IS NOT NULL
GROUP BY co.gmlid, lu.id, lu.class, lu.usage;

CREATE INDEX ON citydb.land_use_footprints USING GIST(geometry);

-- Verify
SELECT COUNT(*) AS land_use_count FROM citydb.land_use_footprints;


-- ── Roads ─────────────────────────────────────────────────────────────────────
-- objectclass_id=45 = Road (verified against citydb.objectclass)
-- All 22,172 Road rows have lod1_multi_surface_id populated.

DROP MATERIALIZED VIEW IF EXISTS citydb.road_footprints;

CREATE MATERIALIZED VIEW citydb.road_footprints AS
SELECT
    co.gmlid,
    tc.class,
    tc.function,
    tc.usage,
    ST_SetSRID(
        ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),
        4326
    )::geometry(Geometry, 4326) AS geometry
FROM citydb.transportation_complex tc
JOIN citydb.cityobject co ON co.id = tc.id
JOIN citydb.surface_geometry sg ON sg.root_id = tc.lod1_multi_surface_id
WHERE tc.objectclass_id = 45
  AND sg.geometry IS NOT NULL
GROUP BY co.gmlid, tc.id, tc.class, tc.function, tc.usage;

CREATE INDEX ON citydb.road_footprints USING GIST(geometry);

-- Verify
SELECT COUNT(*) AS road_count FROM citydb.road_footprints;


-- ── Flood Zones (WaterBody) ───────────────────────────────────────────────────
-- Uses lod1_multi_surface_id (all 1,740 waterbody rows have this populated;
-- lod0_multi_surface_id is unpopulated in Taito-ku 2024 data).

DROP MATERIALIZED VIEW IF EXISTS citydb.flood_zone_footprints;

CREATE MATERIALIZED VIEW citydb.flood_zone_footprints AS
SELECT
    co.gmlid,
    wb.class,
    wb.function,
    wb.usage,
    ST_SetSRID(
        ST_FlipCoordinates(ST_Force2D(ST_Union(sg.geometry))),
        4326
    )::geometry(Geometry, 4326) AS geometry
FROM citydb.waterbody wb
JOIN citydb.cityobject co ON co.id = wb.id
JOIN citydb.surface_geometry sg ON sg.root_id = wb.lod1_multi_surface_id
WHERE sg.geometry IS NOT NULL
GROUP BY co.gmlid, wb.id, wb.class, wb.function, wb.usage;

CREATE INDEX ON citydb.flood_zone_footprints USING GIST(geometry);

-- Verify
SELECT COUNT(*) AS flood_zone_count FROM citydb.flood_zone_footprints;
