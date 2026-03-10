-- Migration 004: Feature versioning table
-- Creates citydb.feature_versions and seeds v1 records for all existing features.

-- ── Create table ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS citydb.feature_versions (
    id          bigserial PRIMARY KEY,
    gmlid       varchar  NOT NULL,
    version     int      NOT NULL,
    status      varchar  NOT NULL,       -- 'current' | 'archived' | 'deleted'
    source_tag  varchar,                 -- 'PLATEAU-2024', 'manual-edit'
    change_type varchar,                 -- 'import' | 'attr_update' | 'geom_lod1' | 'geom_lod2' | 'delete'
    attributes  jsonb,
    changed_at  timestamptz NOT NULL DEFAULT now(),
    change_note varchar,
    UNIQUE (gmlid, version)
);

CREATE INDEX IF NOT EXISTS feature_versions_gmlid_status_idx ON citydb.feature_versions (gmlid, status);
CREATE INDEX IF NOT EXISTS feature_versions_gmlid_idx ON citydb.feature_versions (gmlid);

-- ── Seed v1: Buildings ────────────────────────────────────────────────────────

INSERT INTO citydb.feature_versions (gmlid, version, status, source_tag, change_type, attributes, changed_at)
SELECT
    co.gmlid,
    1,
    'current',
    'PLATEAU-2024',
    'import',
    jsonb_build_object(
        'measured_height',      b.measured_height,
        'storeys_above_ground', b.storeys_above_ground,
        'usage',                b.usage,
        'class',                b.class,
        'has_lod1',             (b.lod1_solid_id IS NOT NULL),
        'has_lod2',             (b.lod2_solid_id IS NOT NULL)
    ),
    COALESCE(co.creation_date, now())
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
WHERE b.building_root_id = b.id
ON CONFLICT (gmlid, version) DO NOTHING;

-- ── Seed v1: Bridges ─────────────────────────────────────────────────────────

INSERT INTO citydb.feature_versions (gmlid, version, status, source_tag, change_type, attributes, changed_at)
SELECT
    co.gmlid,
    1,
    'current',
    'PLATEAU-2024',
    'import',
    jsonb_build_object(
        'class',    br.class,
        'function', br.function,
        'usage',    br.usage,
        'has_lod1', (br.lod1_solid_id IS NOT NULL)
    ),
    COALESCE(co.creation_date, now())
FROM citydb.bridge br
JOIN citydb.cityobject co ON co.id = br.id
ON CONFLICT (gmlid, version) DO NOTHING;

-- ── Seed v1: City Furniture ───────────────────────────────────────────────────

INSERT INTO citydb.feature_versions (gmlid, version, status, source_tag, change_type, attributes, changed_at)
SELECT
    co.gmlid,
    1,
    'current',
    'PLATEAU-2024',
    'import',
    jsonb_build_object(
        'class',    cf.class,
        'function', cf.function,
        'usage',    cf.usage
    ),
    COALESCE(co.creation_date, now())
FROM citydb.city_furniture cf
JOIN citydb.cityobject co ON co.id = cf.id
ON CONFLICT (gmlid, version) DO NOTHING;

-- ── Seed v1: Plant Cover ──────────────────────────────────────────────────────

INSERT INTO citydb.feature_versions (gmlid, version, status, source_tag, change_type, attributes, changed_at)
SELECT
    co.gmlid,
    1,
    'current',
    'PLATEAU-2024',
    'import',
    jsonb_build_object(
        'class',    pc.class,
        'function', pc.function,
        'usage',    pc.usage
    ),
    COALESCE(co.creation_date, now())
FROM citydb.plant_cover pc
JOIN citydb.cityobject co ON co.id = pc.id
ON CONFLICT (gmlid, version) DO NOTHING;

-- ── Seed v1: Land Use ────────────────────────────────────────────────────────

INSERT INTO citydb.feature_versions (gmlid, version, status, source_tag, change_type, attributes, changed_at)
SELECT
    co.gmlid,
    1,
    'current',
    'PLATEAU-2024',
    'import',
    jsonb_build_object(
        'class',    lu.class,
        'function', lu.function,
        'usage',    lu.usage
    ),
    COALESCE(co.creation_date, now())
FROM citydb.land_use lu
JOIN citydb.cityobject co ON co.id = lu.id
ON CONFLICT (gmlid, version) DO NOTHING;

-- ── Seed v1: Roads ───────────────────────────────────────────────────────────

INSERT INTO citydb.feature_versions (gmlid, version, status, source_tag, change_type, attributes, changed_at)
SELECT
    co.gmlid,
    1,
    'current',
    'PLATEAU-2024',
    'import',
    jsonb_build_object(
        'class',    tc.class,
        'function', tc.function,
        'usage',    tc.usage
    ),
    COALESCE(co.creation_date, now())
FROM citydb.transportation_complex tc
JOIN citydb.cityobject co ON co.id = tc.id
ON CONFLICT (gmlid, version) DO NOTHING;

-- ── Seed v1: Water Bodies (flood zones) ──────────────────────────────────────

INSERT INTO citydb.feature_versions (gmlid, version, status, source_tag, change_type, attributes, changed_at)
SELECT
    co.gmlid,
    1,
    'current',
    'PLATEAU-2024',
    'import',
    jsonb_build_object(
        'class',    wb.class,
        'function', wb.function,
        'usage',    wb.usage
    ),
    COALESCE(co.creation_date, now())
FROM citydb.waterbody wb
JOIN citydb.cityobject co ON co.id = wb.id
ON CONFLICT (gmlid, version) DO NOTHING;
