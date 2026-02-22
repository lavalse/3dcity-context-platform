# Architecture

## Goal

A prototype that lets Tokyo Taito-ku city staff ask natural language questions about the ward's 3D city model data and get answers backed by real spatial database queries. The system is designed to be transparent: the generated SQL is always shown to the user before execution.

## System Overview

```
City Staff (Japanese / English)
          │
          │  natural language question
          ▼
┌─────────────────────────────────────────────────────────┐
│                   Frontend (Browser)                    │
│  - Query input (NL text)                               │
│  - SQL display (generated SQL, editable)               │
│  - Results table                                        │
│  - Basic map view (GeoJSON overlay)                    │
└────────────────────┬────────────────────────────────────┘
                     │  HTTP POST /api/query
                     ▼
┌─────────────────────────────────────────────────────────┐
│                FastAPI Backend (Python)                 │
│                                                         │
│  1. Schema Context Builder                              │
│     - Loads relevant table descriptions                 │
│     - Injects PLATEAU codelist values                   │
│     - Selects few-shot SQL examples                     │
│                                                         │
│  2. SQL Generator (Claude API)                          │
│     - System prompt: schema context + codelists         │
│     - User prompt: natural language question            │
│     - Returns: SQL query + explanation                  │
│                                                         │
│  3. SQL Runner (asyncpg)                                │
│     - Read-only DB user (SELECT only)                   │
│     - Auto-injects LIMIT 1000 if missing                │
│     - 30-second query timeout                           │
│     - Returns: rows + column names + row count          │
└────────────────────┬────────────────────────────────────┘
                     │  SQL
                     ▼
┌─────────────────────────────────────────────────────────┐
│       PostgreSQL 15 + PostGIS + 3DCityDB v4             │
│                                                         │
│  Schema: citydb                                         │
│  Data: Taito-ku 2024 PLATEAU CityGML                   │
│  Feature types: bldg, tran, luse, fld, urf, brid       │
│  CRS: JGD2011 geographic 2D (EPSG:6668)                │
└─────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Backend (`backend/`)

| Module | Purpose |
|---|---|
| `app/main.py` | FastAPI app setup, CORS, route mounting |
| `app/config.py` | Settings from environment variables |
| `app/database.py` | asyncpg connection pool, query execution |
| `app/api/query.py` | POST `/api/query` — main NL-to-SQL endpoint |
| `app/api/health.py` | GET `/api/health` — DB connectivity check |
| `app/services/sql_generator.py` | Calls Claude API with schema context |
| `app/services/sql_runner.py` | Validates and executes SQL safely |
| `app/services/schema_context.py` | Builds LLM prompt context from schema docs |
| `app/prompts/` | Schema descriptions and few-shot examples (Markdown) |

### Frontend (`frontend/`)

Single-page HTML application, no build step required. Served by nginx in Docker, or directly from the filesystem during development.

### Infrastructure (`infra/`)

- `infra/nginx/nginx.conf` — Reverse proxy: routes `/api/*` to backend, serves frontend static files

### Data (`data/`)

- `data/citygml/` — Downloaded PLATEAU CityGML files (not committed, can be gigabytes)
- `data/import/run-import.sh` — Runs `3dcitydb/impexp` Docker image to load GML into DB

## Key Technical Decisions

### Why 3DCityDB v4 (not v5)?

3DCityDB v5 (released March 2025) uses a generic `PROPERTY` table for all attributes. While more flexible, this makes SQL hard to read and hard for an LLM to generate correctly. For example:

```sql
-- v5: requires knowing property_name string and type casting
SELECT p.val_double FROM property p
JOIN feature f ON f.id = p.feature_id
WHERE f.objectclass_id = 26 AND p.name = 'measuredHeight';

-- v4: direct, readable column
SELECT b.measured_height FROM building b;
```

v4 maps CityGML 2.0 concepts directly to columns. PLATEAU data is CityGML 2.0. This combination produces LLM-friendly SQL.

### Why NL-to-SQL (not SPARQL or CQL)?

- City staff are not technical; SQL results are easy to display as tables
- The schema is well-structured enough for direct SQL
- SPARQL would require a knowledge graph layer (added complexity)
- CQL2 (citydb-tool) is only for data export, not ad-hoc analysis

### Why Show the SQL to the User?

Trust and transparency. City staff should be able to verify what the system queried. This also lets them spot errors and refine questions.

### PLATEAU-Specific Challenges

1. **Codelists**: `bldg:function` codes like `'0401'` mean "residential" — the LLM must know these mappings to generate correct WHERE clauses.

2. **uro: ADE attributes**: PLATEAU's urban planning attributes (`uro:buildingStructureType`, `uro:orgUsage`) are stored as generic attributes in 3DCityDB v4. Their exact storage location depends on how the importer handles the ADE schema.

3. **Geometry CRS**: All geometries are in JGD2011 (EPSG:6668). Spatial queries use PostGIS functions (`ST_Intersects`, `ST_Within`, `ST_DWithin`).

## Data Flow: Query Lifecycle

```
1. User types: "台東区で1981年以前に建てられた木造建物は何棟ありますか？"
   (How many wooden buildings in Taito-ku were built before 1981?)

2. Schema context builder injects:
   - BUILDING table description (measured_height, year_of_construction, etc.)
   - uro:buildingStructureType codelist (1 = 木造, 2 = 鉄骨造, 3 = RC造, ...)
   - Few-shot example of a similar construction-year query

3. Claude API returns:
   SELECT COUNT(*) AS building_count
   FROM citydb.building b
   JOIN citydb.cityobject co ON co.id = b.id
   WHERE b.year_of_construction < 1981
     AND b.year_of_construction IS NOT NULL;
   -- (plus uro join for structure type when ADE is available)

4. SQL displayed to user, user confirms or edits.

5. asyncpg executes against PostgreSQL (read-only user, 30s timeout).

6. Results returned: {"columns": ["building_count"], "rows": [[1247]], "count": 1}
```

## Future Directions

- **Map visualization**: Highlight result buildings on a 2D/3D map (Cesium, Maplibre GL)
- **Saved queries**: Let staff save and share useful queries
- **Multi-dataset joins**: Join building data with flood zones, urban planning zones
- **Export**: Download results as CSV or GeoJSON
- **Auth**: Taito-ku staff login (currently open, prototype only)
