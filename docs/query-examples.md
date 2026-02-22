# Query Examples

Representative natural language queries that city staff might ask, with their corresponding SQL. These also serve as few-shot examples for the LLM SQL generator.

## Building Inventory Queries

### Q: How many buildings are in Taito-ku?
```sql
SELECT COUNT(*) AS total_buildings
FROM citydb.building b
WHERE b.building_root_id = b.id;
```

### Q: How many wooden buildings are there in Taito-ku? (台東区の木造建物の数は？)
```sql
SELECT COUNT(*) AS wooden_building_count
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
LEFT JOIN citydb.cityobject_genericattrib ga
    ON ga.cityobject_id = co.id
    AND ga.attrname = 'uro:buildingStructureType'
WHERE b.building_root_id = b.id
  AND ga.strval = '601';  -- 601 = 木造・土蔵造 (wood)
```

### Q: How many buildings were built before the 1981 earthquake resistance standard?
```sql
SELECT COUNT(*) AS pre_1981_buildings
FROM citydb.building b
WHERE b.building_root_id = b.id
  AND b.year_of_construction < 1981
  AND b.year_of_construction IS NOT NULL;
```

### Q: Show the 10 tallest buildings in Taito-ku with their heights and addresses.
```sql
SELECT
    co.gmlid,
    b.measured_height AS height_m,
    b.storeys_above_ground AS floors,
    b.function AS function_code,
    a.street,
    a.house_number
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
LEFT JOIN citydb.address_to_building ab ON ab.building_id = b.id
LEFT JOIN citydb.address a ON a.id = ab.address_id
WHERE b.building_root_id = b.id
  AND b.measured_height IS NOT NULL
ORDER BY b.measured_height DESC
LIMIT 10;
```

## Usage Type Queries

### Q: How many residential buildings are there? (住宅の数は？)
```sql
SELECT COUNT(*) AS residential_count
FROM citydb.building b
WHERE b.building_root_id = b.id
  AND b.function IN ('0401', '0402', '0403');
-- 0401 = 専用住宅, 0402 = 共同住宅, 0403 = 店舗等併用住宅
```

### Q: Show building counts by usage type.
```sql
SELECT
    b.function AS function_code,
    CASE b.function
        WHEN '0401' THEN '専用住宅'
        WHEN '0402' THEN '共同住宅'
        WHEN '0403' THEN '店舗等併用住宅'
        WHEN '0501' THEN '官公庁施設'
        WHEN '0502' THEN '文教厚生施設'
        WHEN '0503' THEN '宗教施設'
        WHEN '0504' THEN '医療施設'
        WHEN '0506' THEN '工場・倉庫等'
        WHEN '0507' THEN '商業・業務施設'
        WHEN '0508' THEN '運輸・通信施設'
        ELSE 'その他 / 不明'
    END AS function_label,
    COUNT(*) AS count
FROM citydb.building b
WHERE b.building_root_id = b.id
GROUP BY b.function
ORDER BY count DESC;
```

### Q: Show building counts by structure type. (構造種別の建物数は？)
```sql
SELECT
    ga.strval AS structure_code,
    CASE ga.strval
        WHEN '601' THEN '木造・土蔵造'
        WHEN '602' THEN '鉄骨鉄筋コンクリート造'
        WHEN '603' THEN '鉄筋コンクリート造'
        WHEN '604' THEN '鉄骨造'
        WHEN '605' THEN '石造'
        WHEN '606' THEN 'レンガ造'
        WHEN '607' THEN 'コンクリートブロック造'
        WHEN '609' THEN 'その他'
        WHEN '610' THEN '不明'
        ELSE ga.strval
    END AS structure_label,
    COUNT(*) AS count
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
LEFT JOIN citydb.cityobject_genericattrib ga
    ON ga.cityobject_id = co.id
    AND ga.attrname = 'uro:buildingStructureType'
WHERE b.building_root_id = b.id
GROUP BY ga.strval
ORDER BY count DESC;
```

## Disaster Risk Queries

### Q: How many wooden buildings are 3 stories or taller? (3階建て以上の木造建物は？)
```sql
SELECT COUNT(*) AS count
FROM citydb.building b
JOIN citydb.cityobject co ON co.id = b.id
LEFT JOIN citydb.cityobject_genericattrib ga
    ON ga.cityobject_id = co.id
    AND ga.attrname = 'uro:buildingStructureType'
WHERE b.building_root_id = b.id
  AND ga.strval = '601'
  AND b.storeys_above_ground >= 3;
```

### Q: Average building height by construction decade.
```sql
SELECT
    (b.year_of_construction / 10) * 10 AS decade,
    COUNT(*) AS count,
    ROUND(AVG(b.measured_height)::numeric, 1) AS avg_height_m,
    MAX(b.measured_height) AS max_height_m
FROM citydb.building b
WHERE b.building_root_id = b.id
  AND b.year_of_construction IS NOT NULL
  AND b.measured_height IS NOT NULL
GROUP BY decade
ORDER BY decade;
```

## Height Analysis Queries

### Q: How many buildings are over 31 meters tall? (31m超の建物は？)
```sql
SELECT COUNT(*) AS count
FROM citydb.building b
WHERE b.building_root_id = b.id
  AND b.measured_height > 31;
```

### Q: Building height distribution.
```sql
SELECT
    CASE
        WHEN b.measured_height < 10 THEN '< 10m (1-3F)'
        WHEN b.measured_height < 20 THEN '10-20m (4-6F)'
        WHEN b.measured_height < 31 THEN '20-31m (7-10F)'
        WHEN b.measured_height < 60 THEN '31-60m (中高層)'
        ELSE '>= 60m (超高層)'
    END AS height_range,
    COUNT(*) AS count
FROM citydb.building b
WHERE b.building_root_id = b.id
  AND b.measured_height IS NOT NULL
GROUP BY height_range
ORDER BY MIN(b.measured_height);
```

## Data Quality Checks

### Q: What percentage of buildings have complete attribute data?
```sql
SELECT
    COUNT(*) AS total,
    ROUND(100.0 * COUNT(measured_height) / COUNT(*), 1) AS pct_has_height,
    ROUND(100.0 * COUNT(storeys_above_ground) / COUNT(*), 1) AS pct_has_floors,
    ROUND(100.0 * COUNT(year_of_construction) / COUNT(*), 1) AS pct_has_year,
    ROUND(100.0 * COUNT(function) / COUNT(*), 1) AS pct_has_function
FROM citydb.building b
WHERE b.building_root_id = b.id;
```
