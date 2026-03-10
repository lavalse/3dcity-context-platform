# Taito-ku CityGML Data Report

台東区 3D都市モデル データ調査レポート

**Dataset:** Tokyo Taito-ku (台東区) PLATEAU 3D City Model 2024
**Source:** Japan MLIT PLATEAU project — CC BY 4.0
**Portal:** https://www.geospatial.jp/ckan/dataset/plateau-13106-taito-ku-2024
**Imported into:** 3DCityDB v4 on PostgreSQL 15 + PostGIS
**Database size:** 4.6 GB

---

## 1. Feature Types in the Database

| Feature Type | Class Name | Count | Description |
|---|---|---|---|
| `bldg` | Building | **72,485** | Top-level buildings (root only) |
| `bldg` | BuildingWallSurface | 416,607 | LOD2 wall surfaces |
| `bldg` | BuildingRoofSurface | 174,048 | LOD2 roof surfaces |
| `bldg` | BuildingGroundSurface | 47,298 | LOD2 ground surfaces |
| `bldg` | BuildingInstallation | 528 | Attached structures (canopies, etc.) |
| `luse` | LandUse | **188,273** | Land use zone polygons |
| `tran` | Road | **22,172** | Road centrelines / surfaces |
| `tran` | TrafficArea | 25,769 | Carriageway surfaces |
| `tran` | AuxiliaryTrafficArea | 765 | Footpaths, medians |
| `fld` | WaterBody | **1,740** | River flood hazard zone polygons |
| `htd` | WaterBody | **7,021** | High-tide flood hazard zone polygons |
| `brid` | Bridge | **59** | Bridge structures |
| `brid` | BridgeWallSurface | 1,605 | Bridge wall surfaces |
| `brid` | BridgeGroundSurface | 68 | Bridge ground surfaces |
| `brid` | BridgeRoofSurface | 15 | Bridge roof surfaces |
| `brid` | BridgeConstructionElement | 541 | Bridge construction elements |
| `frn` | CityFurniture | **7,193** | Street furniture: poles, signs, lights |
| `veg` | SolitaryVegetationObject | **10,191** | Individual trees and shrubs |
| `veg` | PlantCover | 238 | Vegetation area polygons |
| `dem` | ReliefFeature | **18** | DEM relief feature containers |
| `dem` | TINRelief | 18 | TIN elevation model tiles |

> Buildings are stored with both LOD1 (block solid) and LOD2 (detailed surfaces with roof/wall breakdown) geometry.
> River flood zones (fld) and high-tide flood zones (htd) are both stored as `WaterBody` (objectclass_id=9) in `citydb.waterbody` — total 8,761 water body records.

---

## 2. Building Data

### 2.1 Summary Statistics

| Metric | Value |
|---|---|
| Total top-level buildings | 72,486 |
| With measured height | 71,249 (98.3%) |
| Average height | 13.5 m |
| Tallest building | 355.5 m |
| With floor count | 50,059 (69.1%) |
| Floor count unknown (sentinel 9999) | 22,427 (30.9%) |
| Year of construction | **0** — not in this dataset |

### 2.2 Building Usage Breakdown

Usage codes come from `bldg:usage` in CityGML → stored in `citydb.building.usage`.

| Code | Usage (Japanese) | Usage (English) | Count | % |
|---|---|---|---|---|
| 411 | 住宅 | Detached house | 21,807 | 30.1% |
| 461 | 不明 | Unknown | 15,195 | 21.0% |
| 413 | 店舗等併用住宅 | House with shop | 11,165 | 15.4% |
| 412 | 共同住宅 | Apartment / condominium | 9,061 | 12.5% |
| 401 | 業務施設 | Office / business | 5,853 | 8.1% |
| 415 | 作業所併用住宅 | House with workshop | 2,898 | 4.0% |
| 422 | 文教厚生施設 | Education / welfare | 2,327 | 3.2% |
| 402 | 商業施設 | Commercial / retail | 1,504 | 2.1% |
| 431 | 運輸倉庫施設 | Transport / warehouse | 840 | 1.2% |
| 454 | その他 | Other | 610 | 0.8% |
| 403 | 宿泊施設 | Accommodation / hotel | 548 | 0.8% |
| 441 | 工場 | Factory / industrial | 355 | 0.5% |
| 421 | 官公庁施設 | Government / public | 166 | 0.2% |
| 452 | (452) | (unmapped code) | 157 | 0.2% |

**Residential total (411+412+413+414+415):** 44,931 buildings (62%)

### 2.3 Height Distribution

| Height Range | Count | Notes |
|---|---|---|
| No data (-9999) | 1,237 | Height could not be measured |
| < 10 m (≈1–3F) | 32,998 | Majority — low-rise residential |
| 10–20 m (≈4–6F) | 26,984 | Mid-rise apartments |
| 20–31 m (≈7–10F) | 6,804 | Upper mid-rise |
| 31–60 m (mid-rise) | 4,378 | Above fire prevention threshold |
| ≥ 60 m (high-rise) | 85 | Skyscrapers / towers |

### 2.4 Notable Buildings (Top 5 by Height)

| Height (m) | Floors | Usage | Notes |
|---|---|---|---|
| 355.5 | 31 | 402 商業 | Almost certainly Tokyo Skytree (634m antenna not measured as building height) |
| 155.1 | 27 | 401 業務 | Major office tower |
| 148.7 | unknown | 461 不明 | High-rise, usage not recorded |
| 144.2 | 31 | 401 業務 | Office tower |
| 139.2 | unknown | 461 不明 | High-rise, usage not recorded |

---

## 3. Available Attributes

### 3.1 What IS Available (populated in DB)

| Attribute | DB Column | Coverage | Notes |
|---|---|---|---|
| Height | `building.measured_height` | 98.3% | Aerial photogrammetry 2023; -9999 = no data |
| Floors above ground | `building.storeys_above_ground` | 69.1% | 9999 = unknown |
| Floors below ground | `building.storeys_below_ground` | Partial | 9999 = unknown |
| Usage code | `building.usage` | ~98% | 21% coded as 461=Unknown |
| Class | `building.class` | 100% | All = 3001 (standard building class) |
| LOD1 geometry | `surface_geometry` | 100% | Block-level 3D solid |
| LOD2 geometry | `surface_geometry` | ~100% | Detailed with roof/wall/ground surfaces |
| Bounding box | `cityobject.envelope` | 100% | Used for fast spatial indexing |
| GML ID | `cityobject.gmlid` | 100% | Unique identifier e.g. `bldg_xxxxxxxx` |

### 3.2 What is NOT Available

| Attribute | Reason |
|---|---|
| Year of construction | Not surveyed in Taito-ku 2024 dataset |
| Building function (`bldg:function`) | PLATEAU uses `bldg:usage` instead |
| Street address | Not included in this import |
| `uro:buildingStructureType` | PLATEAU ADE — dropped by standard importer (see §5) |
| `uro:detailedUsage` | PLATEAU ADE — dropped |
| `uro:fireproofStructureType` | PLATEAU ADE — dropped |
| `uro:RiverFloodingRiskAttribute` | PLATEAU ADE — dropped |
| Urban planning zones (`urf:`) | ADE feature type — not importable with standard importer |

---

## 4. Data Relationships

```
citydb.cityobject          (every feature — universal parent)
    │  id, objectclass_id, gmlid, envelope
    │
    ├── citydb.building    (buildings and building parts)
    │       id (FK → cityobject)
    │       building_root_id  → points to top-level building
    │       building_parent_id → parent in part hierarchy
    │       measured_height, storeys_above_ground
    │       usage, class
    │       lod1_solid_id, lod2_solid_id  → surface_geometry
    │
    ├── citydb.thematic_surface   (LOD2 wall/roof/ground surfaces)
    │       building_id (FK → building)
    │       objectclass_id: 33=Wall, 34=Roof, 35=Ground
    │       lod2_multi_surface_id → surface_geometry
    │
    ├── citydb.surface_geometry   (actual 3D geometry)
    │       geometry (PostGIS PolyhedralSurface / Polygon)
    │       solid_geometry (PostGIS Polyhedron for LOD1 solids)
    │       parent_id, root_id  (tree structure)
    │
    ├── citydb.land_use    (land use polygons)
    │       id (FK → cityobject)
    │       class, function, usage
    │       lod1_multi_surface_id → surface_geometry
    │
    ├── citydb.waterbody   (flood hazard zones — fld river + htd high-tide)
    │       id (FK → cityobject)
    │       objectclass_id = 9  (8,761 total: 1,740 fld + 7,021 htd)
    │
    ├── citydb.bridge      (bridge structures)
    │       id (FK → cityobject)
    │       59 bridges; thematic surfaces via bridge_thematic_surface
    │
    ├── citydb.city_furniture  (street poles, signs, lights)
    │       id (FK → cityobject)
    │       lod1_geometry_id, lod2_geometry_id → surface_geometry
    │       7,193 objects
    │
    ├── citydb.plant_cover / citydb.solitary_vegetat_object  (vegetation)
    │       id (FK → cityobject)
    │       10,191 SolitaryVegetationObject + 238 PlantCover
    │
    ├── citydb.relief_feature / citydb.tin_relief  (DEM elevation)
    │       id (FK → cityobject)
    │       18 TIN tiles covering Taito-ku
    │
    └── citydb.cityobject_genericattrib  (overflow attributes)
            cityobject_id (FK → cityobject)
            attrname (e.g. 'uro:buildingStructureType')
            strval / intval / realval
```

### Key JOIN Pattern

Almost every query needs this filter to avoid double-counting building parts:

```sql
WHERE b.building_root_id = b.id   -- top-level buildings only
```

---

## 5. Known Limitations

### PLATEAU ADE Attributes Dropped

The PLATEAU CityGML uses a custom Application Domain Extension (`uro:` namespace) for attributes like structure type, detailed usage, and flood risk depth. The standard 3DCityDB importer does not load the PLATEAU ADE schema, so these attributes are silently discarded during import.

**Impact:** The following richer attributes are unavailable in the current DB:
- `uro:buildingStructureType` — wood, RC, SRC, steel frame etc.
- `uro:detailedUsage` — more granular usage classification
- `uro:fireproofStructureType` — fire resistance classification
- `uro:RiverFloodingRiskAttribute` — per-building flood depth by river/return period

**Workaround (future work):** Load the PLATEAU ADE extension schema into the importer before importing CityGML files. The PLATEAU GitHub repository provides the ADE schema definition.

### Urban Planning Zones (urf:) Not Imported

The `urf:` feature type (用途地域, 防火地域, etc.) uses PLATEAU ADE classes and is not recognized by the standard 3DCityDB importer. These 11 zone types returned 0 records.

### Flood Zones as WaterBody

Flood hazard zones (`fld:`) were imported as the standard CityGML `WaterBody` class (`objectclass_id = 9`) rather than a dedicated hazard class. Spatial overlap queries work correctly, but the flood depth attribute per return period is not stored.

### Coordinate System

All geometries are stored in **EPSG:6668** (JGD2011 geographic 2D — longitude/latitude in decimal degrees). For distance calculations in meters, either:
- Cast to geography: `co.envelope::geography`
- Reproject to a metric CRS: `ST_Transform(geom, 6677)` (JGD2011 / Japan Plane CS IX)

---

## 6. Flood Hazard Data

**8,761 total water body polygons** — both river flood and high-tide flood zones, all stored as `WaterBody` (`objectclass_id = 9`).

### River flood zones (fld) — 1,740 polygons

Imported from three river watershed datasets:

| Dataset | River | Description |
|---|---|---|
| Kandagawa | 神田川 | Kanda River urban flooding |
| Arakawa / Kandagawa | 荒川・神田川 | Combined watershed |
| Sumidagawa / Shingashigawa | 隅田川・新川 | Sumida + Shingashi Rivers |

### High-tide flood zones (htd) — 7,021 polygons

Storm surge / high-tide inundation zones (高潮浸水想定区域). Single GML file covering the Taito-ku area.

Spatial overlap with buildings can be queried using `co.envelope && fld_co.envelope` for fast bounding-box pre-filter. To distinguish fld vs htd zones, the `gmlid` prefix differs but there is no separate objectclass — both use objectclass_id = 9.

---

## 7. Data Provenance

| Data Layer | Source | Survey Year |
|---|---|---|
| Building footprints | Tokyo 1/2500 topographic map | 2021 |
| Building heights | Aerial photogrammetry | 2023 |
| LOD2 textures | Aerial photography | 2023 |
| Building attributes (usage, floors) | Tokyo urban planning basic survey (都市計画基礎調査) | 2021 |
| Road network | Tokyo topographic map | 2021 |
| Land use zones | Urban planning map | 2021 |
| Flood hazard zones | River flood inundation simulation | Various |

**CityGML spec:** PLATEAU 3D Urban Model Standard Product Specification v4.1
**CRS in source files:** JGD2011 geographic 3D (EPSG:6697), ellipsoidal heights
**CRS in database:** JGD2011 geographic 2D (EPSG:6668)
**License:** CC BY 4.0 — attribution required: 国土交通省 (MLIT) / Project PLATEAU
