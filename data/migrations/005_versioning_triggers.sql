-- Migration 005: Versioning triggers + backfill missing solitary vegetation v1 records
--
-- 1. Backfill solitary_vegetat_object (missed in 004)
-- 2. Add AFTER INSERT triggers on all 8 feature tables so future imports
--    automatically create v1 version records without any manual SQL.

-- ── 1. Backfill solitary_vegetat_object ──────────────────────────────────────

INSERT INTO citydb.feature_versions (gmlid, version, status, source_tag, change_type, attributes, changed_at)
SELECT
    co.gmlid,
    1,
    'current',
    'PLATEAU-2024',
    'import',
    jsonb_build_object(
        'class',    svo.class,
        'function', svo.function,
        'usage',    svo.usage
    ),
    COALESCE(co.creation_date, now())
FROM citydb.solitary_vegetat_object svo
JOIN citydb.cityobject co ON co.id = svo.id
ON CONFLICT (gmlid, version) DO NOTHING;

-- ── 2. Trigger function: buildings ────────────────────────────────────────────
-- Fires AFTER INSERT on citydb.building.
-- Only creates a version for root buildings (building_root_id = id).
-- cityobject row must already exist (it is always inserted first by the importer).

CREATE OR REPLACE FUNCTION citydb.fv_insert_building()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.building_root_id IS NOT DISTINCT FROM NEW.id THEN
        INSERT INTO citydb.feature_versions
            (gmlid, version, status, source_tag, change_type, attributes)
        SELECT
            co.gmlid, 1, 'current', 'PLATEAU-2024', 'import',
            jsonb_build_object(
                'measured_height',      NEW.measured_height,
                'storeys_above_ground', NEW.storeys_above_ground,
                'usage',                NEW.usage,
                'class',                NEW.class,
                'has_lod1',             (NEW.lod1_solid_id IS NOT NULL),
                'has_lod2',             (NEW.lod2_solid_id IS NOT NULL)
            )
        FROM citydb.cityobject co WHERE co.id = NEW.id
        ON CONFLICT (gmlid, version) DO NOTHING;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_fv_building ON citydb.building;
CREATE TRIGGER trg_fv_building
    AFTER INSERT ON citydb.building
    FOR EACH ROW EXECUTE FUNCTION citydb.fv_insert_building();

-- ── 3. Trigger function: bridge ───────────────────────────────────────────────

CREATE OR REPLACE FUNCTION citydb.fv_insert_bridge()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO citydb.feature_versions
        (gmlid, version, status, source_tag, change_type, attributes)
    SELECT
        co.gmlid, 1, 'current', 'PLATEAU-2024', 'import',
        jsonb_build_object(
            'class',    NEW.class,
            'function', NEW.function,
            'usage',    NEW.usage,
            'has_lod1', (NEW.lod1_solid_id IS NOT NULL)
        )
    FROM citydb.cityobject co WHERE co.id = NEW.id
    ON CONFLICT (gmlid, version) DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_fv_bridge ON citydb.bridge;
CREATE TRIGGER trg_fv_bridge
    AFTER INSERT ON citydb.bridge
    FOR EACH ROW EXECUTE FUNCTION citydb.fv_insert_bridge();

-- ── 4. Trigger function: city_furniture ──────────────────────────────────────

CREATE OR REPLACE FUNCTION citydb.fv_insert_city_furniture()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO citydb.feature_versions
        (gmlid, version, status, source_tag, change_type, attributes)
    SELECT
        co.gmlid, 1, 'current', 'PLATEAU-2024', 'import',
        jsonb_build_object(
            'class',    NEW.class,
            'function', NEW.function,
            'usage',    NEW.usage
        )
    FROM citydb.cityobject co WHERE co.id = NEW.id
    ON CONFLICT (gmlid, version) DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_fv_city_furniture ON citydb.city_furniture;
CREATE TRIGGER trg_fv_city_furniture
    AFTER INSERT ON citydb.city_furniture
    FOR EACH ROW EXECUTE FUNCTION citydb.fv_insert_city_furniture();

-- ── 5. Trigger function: plant_cover ─────────────────────────────────────────

CREATE OR REPLACE FUNCTION citydb.fv_insert_plant_cover()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO citydb.feature_versions
        (gmlid, version, status, source_tag, change_type, attributes)
    SELECT
        co.gmlid, 1, 'current', 'PLATEAU-2024', 'import',
        jsonb_build_object(
            'class',    NEW.class,
            'function', NEW.function,
            'usage',    NEW.usage
        )
    FROM citydb.cityobject co WHERE co.id = NEW.id
    ON CONFLICT (gmlid, version) DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_fv_plant_cover ON citydb.plant_cover;
CREATE TRIGGER trg_fv_plant_cover
    AFTER INSERT ON citydb.plant_cover
    FOR EACH ROW EXECUTE FUNCTION citydb.fv_insert_plant_cover();

-- ── 6. Trigger function: solitary_vegetat_object ─────────────────────────────

CREATE OR REPLACE FUNCTION citydb.fv_insert_solitary_veg()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO citydb.feature_versions
        (gmlid, version, status, source_tag, change_type, attributes)
    SELECT
        co.gmlid, 1, 'current', 'PLATEAU-2024', 'import',
        jsonb_build_object(
            'class',    NEW.class,
            'function', NEW.function,
            'usage',    NEW.usage
        )
    FROM citydb.cityobject co WHERE co.id = NEW.id
    ON CONFLICT (gmlid, version) DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_fv_solitary_veg ON citydb.solitary_vegetat_object;
CREATE TRIGGER trg_fv_solitary_veg
    AFTER INSERT ON citydb.solitary_vegetat_object
    FOR EACH ROW EXECUTE FUNCTION citydb.fv_insert_solitary_veg();

-- ── 7. Trigger function: land_use ────────────────────────────────────────────

CREATE OR REPLACE FUNCTION citydb.fv_insert_land_use()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO citydb.feature_versions
        (gmlid, version, status, source_tag, change_type, attributes)
    SELECT
        co.gmlid, 1, 'current', 'PLATEAU-2024', 'import',
        jsonb_build_object(
            'class',    NEW.class,
            'function', NEW.function,
            'usage',    NEW.usage
        )
    FROM citydb.cityobject co WHERE co.id = NEW.id
    ON CONFLICT (gmlid, version) DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_fv_land_use ON citydb.land_use;
CREATE TRIGGER trg_fv_land_use
    AFTER INSERT ON citydb.land_use
    FOR EACH ROW EXECUTE FUNCTION citydb.fv_insert_land_use();

-- ── 8. Trigger function: transportation_complex ──────────────────────────────

CREATE OR REPLACE FUNCTION citydb.fv_insert_transportation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO citydb.feature_versions
        (gmlid, version, status, source_tag, change_type, attributes)
    SELECT
        co.gmlid, 1, 'current', 'PLATEAU-2024', 'import',
        jsonb_build_object(
            'class',    NEW.class,
            'function', NEW.function,
            'usage',    NEW.usage
        )
    FROM citydb.cityobject co WHERE co.id = NEW.id
    ON CONFLICT (gmlid, version) DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_fv_transportation ON citydb.transportation_complex;
CREATE TRIGGER trg_fv_transportation
    AFTER INSERT ON citydb.transportation_complex
    FOR EACH ROW EXECUTE FUNCTION citydb.fv_insert_transportation();

-- ── 9. Trigger function: waterbody ───────────────────────────────────────────

CREATE OR REPLACE FUNCTION citydb.fv_insert_waterbody()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO citydb.feature_versions
        (gmlid, version, status, source_tag, change_type, attributes)
    SELECT
        co.gmlid, 1, 'current', 'PLATEAU-2024', 'import',
        jsonb_build_object(
            'class',    NEW.class,
            'function', NEW.function,
            'usage',    NEW.usage
        )
    FROM citydb.cityobject co WHERE co.id = NEW.id
    ON CONFLICT (gmlid, version) DO NOTHING;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_fv_waterbody ON citydb.waterbody;
CREATE TRIGGER trg_fv_waterbody
    AFTER INSERT ON citydb.waterbody
    FOR EACH ROW EXECUTE FUNCTION citydb.fv_insert_waterbody();
