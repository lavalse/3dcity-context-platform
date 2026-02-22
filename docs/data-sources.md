# Data Sources: Tokyo Taito-ku PLATEAU CityGML 2024

## Overview

Tokyo Taito-ku (台東区, area code: 13106) 3D city model data is provided free of charge by Japan's Ministry of Land, Infrastructure, Transport and Tourism (MLIT) under the PLATEAU project. The 2024 dataset is licensed **CC BY 4.0**.

- **PLATEAU portal**: https://www.geospatial.jp/ckan/dataset/plateau-13106-taito-ku-2024
- **Ward area**: 10.11 km²
- **Spec version**: PLATEAU 3D Urban Model Standard Product Specification v4.1
- **CityGML version**: 2.0
- **Coordinate reference system**: JGD2011 geographic 3D (EPSG:6697), heights are ellipsoidal

## Downloading the Data

### Option A: Direct ZIP download

```bash
# Full CityGML package (~1-2 GB)
cd data/citygml
wget "https://s3.tlab.cloud/spatialid/tokyo23ku/dl/13106_taito-ku_city_2024_citygml_1_op.zip"
unzip 13106_taito-ku_city_2024_citygml_1_op.zip
```

### Option B: PLATEAU API (individual datasets)

Use the PLATEAU MCP tools or API to get direct file URLs for specific feature types.

## Available Feature Types

| Code | Japanese | English | Coverage |
|---|---|---|---|
| `bldg` | 建築物モデル | Building model | Full ward, LOD1 + LOD2 |
| `tran` | 交通（道路）モデル | Road model | Full ward LOD1/2; Ueno/Asakusa LOD3 |
| `luse` | 土地利用モデル | Land use model | Full ward, LOD1 |
| `fld` | 洪水浸水想定区域 | Flood inundation hazard | 3 river watersheds |
| `htd` | 高潮浸水想定区域 | Storm surge hazard | Applicable zones |
| `lsld` | 土砂災害警戒区域 | Landslide hazard zone | Applicable zones |
| `urf` | 都市計画決定情報 | Urban planning zones | Full ward, 11 zone types |
| `brid` | 橋梁モデル | Bridge model | 5 LOD1, 21 LOD2 bridges |
| `frn` | 都市設備モデル | Urban furniture | Ueno/Asakusa area |
| `veg` | 植生モデル | Vegetation model | LOD0 full ward; LOD1/2 Ueno/Asakusa |
| `shelter` | 避難施設情報 | Evacuation shelters | Full ward |
| `park` | 公園情報 | Park information | Full ward |
| `landmark` | ランドマーク情報 | Landmark information | Full ward |
| `station` | 鉄道駅情報 | Railway station information | Full ward |

## Building Data (bldg) — Key Attributes

### Standard CityGML bldg: attributes (verified in Taito-ku 2024)

| Attribute | DB Column | In DB? | Notes |
|---|---|---|---|
| `bldg:measuredHeight` | `building.measured_height` | **Yes** | -9999 = no measurement; filter `> 0` |
| `bldg:storeysAboveGround` | `building.storeys_above_ground` | **Yes** | 9999 = unknown |
| `bldg:storeysBelowGround` | `building.storeys_below_ground` | Yes | 9999 = unknown |
| `bldg:usage` | `building.usage` | **Yes** | Main use type — see codelist below |
| `bldg:class` | `building.class` | Yes | All = 3001 in this dataset |
| `bldg:function` | `building.function` | No | PLATEAU uses `bldg:usage` instead |
| `bldg:yearOfConstruction` | `building.year_of_construction` | No | Not in Taito-ku 2024 survey |

### PLATEAU uro: ADE attributes (in GML but dropped by importer)

These attributes exist in the CityGML source files but the standard 3DCityDB importer
does not have the PLATEAU `uro:` ADE schema loaded, so they are not stored in the DB.
Fixing this requires a PLATEAU-specific import configuration.

| Attribute | Description | Available in DB? |
|---|---|---|
| `uro:fireproofStructureType` | Fire resistance classification | No (dropped) |
| `uro:detailedUsage` | Detailed usage code | No (dropped) |
| `uro:landUseType` | Land use type at building level | No (dropped) |
| `uro:districtsAndZonesType` | Urban zone classification | No (dropped) |
| `uro:RiverFloodingRiskAttribute` | Flood risk depth by river | No (dropped) |
| `uro:buildingRoofEdgeArea` | Roof area (m²) | No (dropped) |

### Building Usage Codelist (`bldg:usage` → `building.usage`)

| Code | Japanese | English |
|---|---|---|
| 401 | 業務施設 | Office / business |
| 402 | 商業施設 | Commercial / retail |
| 403 | 宿泊施設 | Accommodation |
| 404 | 商業系複合施設 | Mixed commercial |
| 411 | 住宅 | House / detached residence |
| 412 | 共同住宅 | Apartment / condominium |
| 413 | 店舗等併用住宅 | House with shop |
| 414 | 店舗等併用共同住宅 | Apartment with shop |
| 415 | 作業所併用住宅 | House with workshop |
| 421 | 官公庁施設 | Government / public facility |
| 422 | 文教厚生施設 | Education / welfare |
| 431 | 運輸倉庫施設 | Transport / warehouse |
| 441 | 工場 | Factory |
| 454 | その他 | Other |
| 461 | 不明 | Unknown |

### Building Structure Type Codelist (`uro:buildingStructureType`)

| Code | Japanese | English |
|---|---|---|
| 601 | 木造・土蔵造 | Wood / traditional storehouse |
| 602 | 鉄骨鉄筋コンクリート造 | Steel-reinforced concrete (SRC) |
| 603 | 鉄筋コンクリート造 | Reinforced concrete (RC) |
| 604 | 鉄骨造 | Steel frame |
| 605 | 石造 | Stone |
| 606 | レンガ造 | Brick |
| 607 | コンクリートブロック造 | Concrete block |
| 608 | 鉄骨・鉄筋コンクリート造 | Steel and RC |
| 609 | その他 | Other |
| 610 | 不明 | Unknown |

## Flood Hazard Zones (fld)

Three river watershed datasets are available:

| Dataset | Japanese | River |
|---|---|---|
| Kandagawa | 神田川流域 | Kanda River (urban flooding) |
| Arakawa/Kandagawa watershed | 荒川・神田川 | Arakawa + Kanda |
| Sumidagawa/Shingashigawa | 隅田川・新川 | Sumida + Shingashi Rivers |

Each dataset contains flood inundation depth polygons at various return periods.

## Urban Planning Zones (urf)

11 zone types available:

| Zone Type | Japanese |
|---|---|
| UseDistrict | 用途地域 |
| FirePreventionDistrict | 防火地域 / 準防火地域 |
| HeightControlDistrict | 高度地区 |
| DistrictPlan | 地区計画 |
| AreaClassification | 区域区分 |
| HighLevelUseDistrict | 高度利用地区 |
| SpecialUseDistrict | 特別用途地区 |
| ScenicDistrict | 風致地区 |

## Data Sources / Survey Years

- Building footprints: 1/2500 topographic map (Tokyo, 2021 survey)
- Building height: Aerial photogrammetry (Tokyo, 2023)
- Building texture (LOD2): Aerial photography (Tokyo, 2023)
- Building attributes: Urban planning basic survey (都市計画基礎調査, Tokyo, 2021)
- Building names: National basic information (GSI, 2023)

## Import Order (Recommended)

When importing into 3DCityDB, import in this order to avoid foreign key issues:

1. `bldg` (buildings — the primary dataset)
2. `tran` (roads)
3. `luse` (land use)
4. `urf` (urban planning zones)
5. `fld` (flood hazard)
6. `brid`, `frn`, `veg` (secondary features)

See `data/import/run-import.sh` and `docs/setup.md` for the import procedure.
