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

### Standard CityGML bldg: attributes

| Attribute | Storage in 3DCityDB v4 | Description |
|---|---|---|
| `bldg:measuredHeight` | `building.measured_height` | Building height in meters (aerial photogrammetry) |
| `bldg:storeysAboveGround` | `building.storeys_above_ground` | Floors above ground |
| `bldg:storeysBelowGround` | `building.storeys_below_ground` | Floors below ground |
| `bldg:yearOfConstruction` | `building.year_of_construction` | Year built |
| `bldg:yearOfDemolition` | `building.year_of_demolition` | Year demolished (if applicable) |
| `bldg:class` | `building.class` | Building class code |
| `bldg:function` | `building.function` | Building function (use type) — see codelist below |
| `bldg:roofType` | `building.roof_type` | Roof type code |

### PLATEAU uro: ADE attributes (via uro:BuildingDetails)

These are part of PLATEAU's Application Domain Extension for urban objects:

| Attribute | Description |
|---|---|
| `uro:prefecture` | Prefecture code (13 = Tokyo) |
| `uro:city` | Municipality code (13106 = Taito-ku) |
| `uro:surveyYear` | Survey reference year |
| `uro:buildingStructureType` | Structural type — see codelist |
| `uro:buildingRoofEdgeArea` | Roof footprint area (m²) |
| `uro:districtsAndZonesType` | Urban districts/zones classification |
| `uro:orgUsage` | Original building usage from urban planning survey |
| `uro:orgFireproofStructure` | Fire resistance/fireproof classification |

### Building Function Codelist (`bldg:function`)

PLATEAU uses the National Land Numerical Information building usage codes:

| Code | Japanese | English |
|---|---|---|
| 0401 | 専用住宅 | Detached house |
| 0402 | 共同住宅 | Apartment / condominium |
| 0403 | 店舗等併用住宅 | Residence with commercial use |
| 0501 | 官公庁施設 | Government / public facility |
| 0502 | 文教厚生施設 | Education / welfare facility |
| 0503 | 宗教施設 | Religious facility |
| 0504 | 医療施設 | Medical facility |
| 0506 | 工場・倉庫等 | Factory / warehouse |
| 0507 | 商業・業務施設 | Commercial / business facility |
| 0508 | 運輸・通信施設 | Transport / communication facility |
| 0510 | 農林漁業用施設 | Agriculture / fishery facility |

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
