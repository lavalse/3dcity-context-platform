# 3DCityDB v4 Schema Reference

This document describes the key tables and patterns used for querying Taito-ku PLATEAU data in 3DCityDB v4. All tables live in the `citydb` PostgreSQL schema.

## Core Tables

### `citydb.cityobject` — All city objects

Every feature imported from CityGML gets a row here regardless of type.

| Column | Type | Description |
|---|---|---|
| `id` | bigint PK | Internal ID (all other tables FK here) |
| `objectclass_id` | int | Feature type (FK → objectclass) |
| `gmlid` | varchar | Original CityGML gml:id (e.g., `bldg_1234`) |
| `name` | varchar | Object name if provided |
| `creation_date` | timestamptz | When imported |
| `envelope` | geometry | Bounding box in DB CRS (JGD2011 EPSG:6668) |

### `citydb.objectclass` — Feature type registry

| Key objectclass_id | class_name |
|---|---|
| 26 | Building |
| 25 | BuildingPart |
| 27 | BuildingInstallation |
| 33 | WallSurface |
| 34 | RoofSurface |
| 35 | OuterFloorSurface |
| 36 | GroundSurface |
| 43 | Road |
| 57 | LandUse |

### `citydb.building` — Building and BuildingPart attributes

The most important table for city staff queries.

| Column | Type | Description |
|---|---|---|
| `id` | bigint PK/FK | = cityobject.id |
| `building_parent_id` | bigint | Parent building ID (for BuildingPart) |
| `building_root_id` | bigint | Top-level building (always set) |
| `class` | varchar | Building class code |
| `function` | varchar | Function code (e.g., '0401' = detached house) |
| `function_codespace` | varchar | Codelist URI for function |
| `usage` | varchar | Actual usage code |
| `year_of_construction` | int | Year built |
| `year_of_demolition` | int | Year demolished |
| `roof_type` | varchar | Roof type code |
| `measured_height` | numeric | Building height (meters, aerial photogrammetry) |
| `measured_height_unit` | varchar | Height unit (usually 'm') |
| `storeys_above_ground` | int | Floors above ground |
| `storeys_below_ground` | int | Floors below ground |
| `lod1_solid_id` | bigint | FK → surface_geometry (LOD1 solid) |
| `lod2_solid_id` | bigint | FK → surface_geometry (LOD2 solid) |
| `lod1_multi_surface_id` | bigint | FK → surface_geometry (LOD1 surfaces) |

### `citydb.surface_geometry` — Geometry storage

Each LOD solid or surface in `building` references a row here.

| Column | Type | Description |
|---|---|---|
| `id` | bigint PK |  |
| `parent_id` | bigint | Parent geometry (for hierarchy) |
| `root_id` | bigint | Root of geometry tree |
| `is_solid` | int | 1 if solid geometry |
| `is_composite` | int | 1 if composite surface |
| `geometry` | geometry | PostGIS geometry (PolyhedralSurface or Polygon) |
| `solid_geometry` | geometry | Solid geometry (PostGIS Polyhedron) |
| `implicit_geometry` | geometry | Template geometry |
| `cityobject_id` | bigint | FK → cityobject |

### `citydb.thematic_surface` — Building surface decomposition

| Column | Type | Description |
|---|---|---|
| `id` | bigint PK/FK |  |
| `objectclass_id` | int | Surface type (33=Wall, 34=Roof, 36=Ground) |
| `building_id` | bigint | FK → building |
| `lod2_multi_surface_id` | bigint | FK → surface_geometry |

### `citydb.address` — Building addresses

| Column | Type | Description |
|---|---|---|
| `id` | bigint PK |  |
| `street` | varchar | Street name |
| `house_number` | varchar | House number |
| `city` | varchar | City name |
| `country` | varchar | Country code |
| `xal_source` | text | Full xAL address XML |
| `multi_point` | geometry | Address point geometry |

### `citydb.address_to_building` — Address ↔ Building link

| Column | Type |
|---|---|
| `building_id` | bigint |
| `address_id` | bigint |

### `citydb.land_use` — Land use polygons (luse)

| Column | Type | Description |
|---|---|---|
| `id` | bigint PK/FK |  |
| `class` | varchar | Land use class code |
| `function` | varchar | Land use function code |
| `usage` | varchar | Actual usage code |
| `lod1_multi_surface_id` | bigint | FK → surface_geometry |

### Generic Attributes — `citydb.cityobject_genericattrib`

PLATEAU's `uro:` ADE attributes that don't fit standard columns are stored here.

| Column | Type | Description |
|---|---|---|
| `id` | bigint PK |  |
| `attrname` | varchar | Attribute name (e.g., 'uro:buildingStructureType') |
| `datatype` | int | 1=string, 2=int, 3=real, 4=uri, 5=date, 6=measure, 7=group |
| `strval` | varchar | String value |
| `intval` | int | Integer value |
| `realval` | numeric | Numeric value |
| `dateval` | date | Date value |
| `cityobject_id` | bigint | FK → cityobject |

**Note:** When PLATEAU CityGML is imported, ADE attributes may end up here if the importer doesn't have a dedicated ADE schema extension loaded. Always verify with `SELECT DISTINCT attrname FROM citydb.cityobject_genericattrib` after import.

## Common Query Patterns

### All buildings with height and address

```sql
SELECT
    co.gmlid,
    b.measured_height,
    b.storeys_above_ground,
    b.year_of_construction,
    b.function,
    a.street,
    a.house_number
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
LEFT JOIN citydb.address_to_building ab ON ab.building_id = b.id
LEFT JOIN citydb.address a ON a.id = ab.address_id
WHERE b.building_root_id = b.id  -- exclude BuildingParts
ORDER BY b.measured_height DESC NULLS LAST
LIMIT 100;
```

### Buildings by function type

```sql
-- Residential buildings (detached houses + apartments)
SELECT COUNT(*) AS count
FROM citydb.building b
WHERE b.building_root_id = b.id
  AND b.function IN ('0401', '0402');
```

### Buildings constructed before earthquake resistance standard (1981)

```sql
SELECT
    co.gmlid,
    b.year_of_construction,
    b.measured_height,
    b.function
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
WHERE b.building_root_id = b.id
  AND b.year_of_construction < 1981
  AND b.year_of_construction IS NOT NULL
ORDER BY b.year_of_construction;
```

### Building structure type from generic attributes

```sql
SELECT
    co.gmlid,
    b.measured_height,
    ga.strval AS structure_type
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
LEFT JOIN citydb.cityobject_genericattrib ga
    ON ga.cityobject_id = co.id
    AND ga.attrname = 'uro:buildingStructureType'
WHERE b.building_root_id = b.id
LIMIT 100;
```

### Spatial query: buildings in a bounding box

```sql
-- Buildings within approximate Ueno Park area
SELECT
    co.gmlid,
    b.measured_height,
    b.function
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
WHERE b.building_root_id = b.id
  AND co.envelope && ST_MakeEnvelope(
    139.765, 35.710,   -- SW corner (lon, lat)
    139.775, 35.720,   -- NE corner (lon, lat)
    6668               -- JGD2011 SRID
  )
ORDER BY b.measured_height DESC;
```

### Spatial join: buildings in flood hazard zone

```sql
-- Buildings intersecting flood zone polygons
SELECT
    b_co.gmlid AS building_id,
    b.measured_height,
    lu_co.gmlid AS flood_zone_id
FROM citydb.building b
JOIN citydb.cityobject b_co ON b_co.id = b.id
JOIN citydb.surface_geometry b_geom ON b_geom.id = b.lod1_solid_id
JOIN citydb.cityobject lu_co ON lu_co.objectclass_id = 57  -- adjust for fld objectclass
JOIN citydb.surface_geometry lu_geom ON ...  -- depends on feature type
WHERE b.building_root_id = b.id
  AND ST_Intersects(b_geom.geometry, lu_geom.geometry);
```

## Checking What's in Your Database

After import, run these to verify data:

```sql
-- Check imported feature types and counts
SELECT oc.classname, COUNT(*) AS count
FROM citydb.cityobject co
JOIN citydb.objectclass oc ON oc.id = co.objectclass_id
GROUP BY oc.classname
ORDER BY count DESC;

-- Check available building attributes
SELECT
    COUNT(*) AS total_buildings,
    COUNT(measured_height) AS has_height,
    COUNT(storeys_above_ground) AS has_floors,
    COUNT(year_of_construction) AS has_year,
    COUNT(function) AS has_function
FROM citydb.building
WHERE building_root_id = id;

-- Check ADE attributes stored
SELECT attrname, datatype, COUNT(*) AS count
FROM citydb.cityobject_genericattrib
GROUP BY attrname, datatype
ORDER BY count DESC;

-- Height distribution
SELECT
    CASE
        WHEN measured_height < 10 THEN '< 10m'
        WHEN measured_height < 20 THEN '10-20m'
        WHEN measured_height < 31 THEN '20-31m'
        WHEN measured_height < 60 THEN '31-60m'
        ELSE '>= 60m'
    END AS height_range,
    COUNT(*) AS count
FROM citydb.building
WHERE building_root_id = id AND measured_height IS NOT NULL
GROUP BY height_range
ORDER BY height_range;
```

## SRID Notes

All geometries are stored in EPSG:6668 (JGD2011 geographic 2D). When using PostGIS spatial functions:
- Use SRID 6668 in `ST_MakeEnvelope`, `ST_SetSRID`, etc.
- Coordinates are (longitude, latitude) in decimal degrees
- For distance calculations in meters, cast to EPSG:6677 (JGD2011 / Japan Plane Rectangular CS IX) or use `ST_DWithin` with `geography` cast
