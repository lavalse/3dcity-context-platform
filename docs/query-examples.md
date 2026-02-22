# Query Examples

Representative natural language queries that city staff might ask, with their corresponding SQL.
These also serve as few-shot examples for the LLM SQL generator.

## What data is actually available (verified 2026-02-22)

| Attribute | DB Column | Notes |
|---|---|---|
| Building usage type | `building.usage` | Codes 401–461, see codelist below |
| Building height (m) | `building.measured_height` | -9999 = no data, filter with `> 0` |
| Floors above ground | `building.storeys_above_ground` | 9999 = unknown |
| Building class | `building.class` | All = 3001 in this dataset |
| Address | `address` table | Via `address_to_building` |

**NOT available** in PLATEAU 2024 Taito-ku: year of construction, structure type (wood/RC/steel).

## Building Usage Codelist (`building.usage`)

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
| 451 | 農林漁業用施設 | Agriculture / fishery |
| 452 | 供給処理施設 | Utility facility |
| 454 | その他 | Other |
| 461 | 不明 | Unknown |

---

## Building Inventory Queries

### Q: How many buildings are in Taito-ku?
```sql
SELECT COUNT(*) AS total_buildings
FROM citydb.building b
WHERE b.building_root_id = b.id;
```

### Q: How many residential buildings are there? (住宅の数は？)
```sql
SELECT COUNT(*) AS residential_count
FROM citydb.building b
WHERE b.building_root_id = b.id
  AND b.usage IN ('411', '412', '413', '414', '415');
-- 411=住宅, 412=共同住宅, 413=店舗等併用住宅, 414=店舗等併用共同住宅, 415=作業所併用住宅
```

### Q: Show building counts by usage type. (用途別の建物数は？)
```sql
SELECT
    b.usage AS usage_code,
    CASE b.usage
        WHEN '401' THEN '業務施設'
        WHEN '402' THEN '商業施設'
        WHEN '403' THEN '宿泊施設'
        WHEN '404' THEN '商業系複合施設'
        WHEN '411' THEN '住宅'
        WHEN '412' THEN '共同住宅'
        WHEN '413' THEN '店舗等併用住宅'
        WHEN '414' THEN '店舗等併用共同住宅'
        WHEN '415' THEN '作業所併用住宅'
        WHEN '421' THEN '官公庁施設'
        WHEN '422' THEN '文教厚生施設'
        WHEN '431' THEN '運輸倉庫施設'
        WHEN '441' THEN '工場'
        WHEN '454' THEN 'その他'
        WHEN '461' THEN '不明'
        ELSE b.usage
    END AS usage_label,
    COUNT(*) AS count
FROM citydb.building b
WHERE b.building_root_id = b.id
GROUP BY b.usage
ORDER BY count DESC;
```

## Height Analysis Queries

### Q: How many buildings are over 31 meters tall? (31m超の建物は？)
```sql
SELECT COUNT(*) AS count
FROM citydb.building b
WHERE b.building_root_id = b.id
  AND b.measured_height > 31;
-- Note: always use > 0 filter to exclude -9999 sentinel values
```

### Q: Show the 10 tallest buildings.
```sql
SELECT
    co.gmlid,
    b.measured_height AS height_m,
    b.storeys_above_ground AS floors,
    b.usage AS usage_code
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
WHERE b.building_root_id = b.id
  AND b.measured_height > 0
ORDER BY b.measured_height DESC
LIMIT 10;
```

### Q: Building height distribution. (建物の高さ分布は？)
```sql
SELECT
    CASE
        WHEN b.measured_height <= 0  THEN '不明 (no data)'
        WHEN b.measured_height < 10  THEN '< 10m (1-3F)'
        WHEN b.measured_height < 20  THEN '10-20m (4-6F)'
        WHEN b.measured_height < 31  THEN '20-31m (7-10F)'
        WHEN b.measured_height < 60  THEN '31-60m (中高層)'
        ELSE '>= 60m (超高層)'
    END AS height_range,
    COUNT(*) AS count
FROM citydb.building b
WHERE b.building_root_id = b.id
GROUP BY height_range
ORDER BY MIN(b.measured_height);
```

### Q: Average building height by usage type.
```sql
SELECT
    b.usage AS usage_code,
    COUNT(*) AS count,
    ROUND(AVG(b.measured_height)::numeric, 1) AS avg_height_m,
    MAX(b.measured_height) AS max_height_m
FROM citydb.building b
WHERE b.building_root_id = b.id
  AND b.measured_height > 0
GROUP BY b.usage
ORDER BY avg_height_m DESC;
```

## Floor Count Queries

### Q: How many buildings have 5 or more floors? (5階建て以上の建物は？)
```sql
SELECT COUNT(*) AS count
FROM citydb.building b
WHERE b.building_root_id = b.id
  AND b.storeys_above_ground >= 5
  AND b.storeys_above_ground < 9999;  -- exclude unknown sentinel
```

### Q: Floor count distribution.
```sql
SELECT
    CASE
        WHEN b.storeys_above_ground = 9999 THEN '不明'
        WHEN b.storeys_above_ground = 1 THEN '1階'
        WHEN b.storeys_above_ground = 2 THEN '2階'
        WHEN b.storeys_above_ground = 3 THEN '3階'
        WHEN b.storeys_above_ground BETWEEN 4 AND 5 THEN '4-5階'
        WHEN b.storeys_above_ground BETWEEN 6 AND 10 THEN '6-10階'
        ELSE '11階以上'
    END AS floor_range,
    COUNT(*) AS count
FROM citydb.building b
WHERE b.building_root_id = b.id
GROUP BY floor_range
ORDER BY MIN(b.storeys_above_ground);
```

## Spatial Queries (requires tran/luse/fld import)

### Q: Buildings within a bounding box (e.g., near Ueno Park)
```sql
SELECT
    co.gmlid,
    b.measured_height AS height_m,
    b.usage
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
WHERE b.building_root_id = b.id
  AND b.measured_height > 0
  AND co.envelope && ST_MakeEnvelope(
    139.765, 35.710,
    139.775, 35.720,
    6668
  )
ORDER BY b.measured_height DESC;
```

## Data Quality Check

```sql
SELECT
    COUNT(*) AS total_buildings,
    COUNT(NULLIF(b.usage, '')) AS has_usage,
    SUM(CASE WHEN b.measured_height > 0 THEN 1 ELSE 0 END) AS has_valid_height,
    SUM(CASE WHEN b.storeys_above_ground < 9999 THEN 1 ELSE 0 END) AS has_valid_floors
FROM citydb.building b
WHERE b.building_root_id = b.id;
```
