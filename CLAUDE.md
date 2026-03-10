# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Prototype NL-to-SQL application for Tokyo Taito-ku (台東区) city staff to query 3D city model data. City staff type natural language questions; the system generates SQL via Claude API (or keyword-based placeholder), shows the SQL for review, then executes it against a 3DCityDB v4 PostgreSQL database loaded with PLATEAU CityGML data.

## Commands

### Start / Stop

```bash
docker compose up -d                        # Start all services
docker compose up -d --force-recreate backend  # Restart backend (e.g. after .env change)
docker compose logs -f backend              # Stream backend logs
docker compose down                         # Stop all (data preserved)
docker compose down -v                      # Stop and delete volumes
```

### Backend development (local, faster iteration)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://citydb:citydb@localhost:5432/citydb uvicorn app.main:app --reload
```

### Database access

```bash
docker exec -it 3dcitydb-pg psql -U citydb -d citydb
```

pgAdmin UI is at http://localhost:5050 (email: admin@citydb.local, password: admin). Password for the `citydb` server connection: `citydb`.

### Import PLATEAU CityGML data

```bash
# After downloading and unzipping PLATEAU data to data/citygml/
# Standard CityGML 2.0 types (all imported)
./data/import/run-import.sh udx/bldg   # Buildings (72,485)
./data/import/run-import.sh udx/tran   # Roads (22,172)
./data/import/run-import.sh udx/luse   # Land use (188,273)
./data/import/run-import.sh udx/fld    # River flood zones (1,740)
./data/import/run-import.sh udx/brid   # Bridges (59)
./data/import/run-import.sh udx/dem    # DEM elevation (18 ReliefFeature)
./data/import/run-import.sh udx/frn    # City furniture (7,193)
./data/import/run-import.sh udx/htd    # High-tide flood zones (7,021)
./data/import/run-import.sh udx/veg    # Vegetation (10,191 + 238 PlantCover)

# PLATEAU ADE types (urf: / lsld:) — 0 objects imported; ADE not supported by standard importer
# ./data/import/run-import.sh udx/urf
# ./data/import/run-import.sh udx/lsld
```

### Verify data import

```bash
docker exec 3dcitydb-pg psql -U citydb -d citydb -c "
SELECT oc.classname, COUNT(*) FROM citydb.cityobject co
JOIN citydb.objectclass oc ON oc.id = co.objectclass_id
GROUP BY oc.classname ORDER BY count DESC;"
```

### Create materialized views for map tiles

After importing data, create materialized views that transform 3DCityDB data to tile-ready format (EPSG:4326) for Martin MVT tile server:

```bash
docker exec -i 3dcitydb-pg psql -U citydb -d citydb < data/migrations/001_building_footprints_mv.sql
docker exec -i 3dcitydb-pg psql -U citydb -d citydb < data/migrations/002_additional_layers_mv.sql
docker compose restart martin  # Restart Martin to discover new views
```

This creates 4 materialized views: `building_footprints`, `land_use_footprints`, `road_footprints`, `flood_zone_footprints`. **Required for the map to display buildings and other layers.**

## LLM Mode vs Placeholder Mode

The backend has two modes controlled by `ANTHROPIC_API_KEY` in `.env`:

- **Placeholder mode** (default, no key): keyword rules in `sql_generator.py` match questions to ~9 hardcoded SQL patterns. Fast, offline, limited.
- **Claude API mode** (key set): Claude generates SQL from the schema description in `backend/app/prompts/system_prompt.md`. Handles any natural language.

To switch: set `ANTHROPIC_API_KEY=sk-ant-...` in `.env`, then `docker compose up -d --force-recreate backend`. The `/api/health` endpoint shows `"llm_mode": "claude_api"` or `"placeholder"`.

**Important:** leave `ANTHROPIC_API_KEY=` (empty) in `.env` for placeholder mode. The old placeholder value `sk-ant-...` in `.env.example` was a bug — it triggered LLM mode with an invalid key, causing 500 errors.

## Architecture

```
browser
  └── nginx :3000  (serves frontend/index.html, proxies /api/*)
        └── FastAPI :8000
              ├── Anthropic Claude API  (NL → SQL, only when key set)
              └── asyncpg → PostgreSQL :5432  (3DCityDB v4 schema)
```

**Key design decision: 3DCityDB v4, not v5.** PLATEAU data is CityGML 2.0. v4 maps features to explicit readable columns (`measured_height`, `storeys_above_ground`, `usage`). v5's generic `PROPERTY` table would make LLM-generated SQL much harder to produce correctly.

## Backend Module Map

| File | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app, CORS middleware, route mounting, DB pool lifespan |
| `backend/app/config.py` | `Settings` via pydantic-settings; `use_llm` property checks key format |
| `backend/app/database.py` | asyncpg pool, `run_query()` — validates SELECT-only, injects LIMIT, 30s timeout |
| `backend/app/api/query.py` | `POST /api/query` — calls sql_generator then database |
| `backend/app/api/health.py` | `GET /api/health` — DB ping + mode status |
| `backend/app/services/sql_generator.py` | Two-mode SQL generator: Claude API or keyword placeholder |
| `backend/app/services/schema_context.py` | Loads `system_prompt.md` for LLM context |
| `backend/app/prompts/system_prompt.md` | Schema description, codelists, SQL rules given to Claude |

## Database Schema

All tables are in the `citydb` PostgreSQL schema. The current import contains:
- **72,485 buildings**, 188,273 land use polygons, 22,172 road segments, 8,761 water bodies (1,740 fld + 7,021 htd), 59 bridges, 7,193 city furniture, 10,429 vegetation objects, 18 DEM relief features

Key tables:

- `citydb.cityobject` — Universal parent for every feature; holds `gmlid`, `envelope` (bounding box), `objectclass_id`
- `citydb.building` — Building attributes: `measured_height`, `storeys_above_ground`, `usage`, `class`; use `WHERE building_root_id = id` to get only top-level buildings (excludes BuildingParts)
- `citydb.thematic_surface` — LOD2 wall/roof/ground surface breakdown; `objectclass_id`: 33=Roof, 34=Wall, 35=Ground (verified against `citydb.objectclass` table)
- `citydb.surface_geometry` — Actual PostGIS geometries; linked from `building` via `lod1_solid_id` / `lod2_solid_id`
- `citydb.land_use` — Land use zone polygons
- `citydb.waterbody` — Flood hazard zones (both river fld and high-tide htd; objectclass_id=9)
- `citydb.bridge` — Bridge structures (59 bridges)
- `citydb.city_furniture` — Street furniture: poles, signs, lights (7,193 objects)
- `citydb.plant_cover` — Vegetation areas (238 PlantCover); SolitaryVegetationObject (10,191) in cityobject
- `citydb.relief_feature` / `citydb.tin_relief` — DEM elevation TIN (18 tiles)
- `citydb.cityobject_genericattrib` — Key-value store for overflow attributes; PLATEAU `uro:` ADE attributes would land here (currently empty — ADE was dropped during import)

Coordinate system: **EPSG:6668** (JGD2011 geographic 2D, lon/lat degrees). Use this SRID in PostGIS functions.

## Key PLATEAU Codelists

PLATEAU uses `bldg:usage` (→ `building.usage`), **not** `bldg:function`. The `building.function` column is NULL for all Taito-ku buildings.

**Building usage** (`building.usage`):
- `'411'` = 住宅 (detached house)
- `'412'` = 共同住宅 (apartment)
- `'413'` = 店舗等併用住宅 (house with shop)
- `'401'` = 業務施設 (office/business)
- `'402'` = 商業施設 (commercial/retail)
- `'421'` = 官公庁施設 (government)
- `'422'` = 文教厚生施設 (education/welfare)
- `'461'` = 不明 (unknown)

Full codelist and data statistics in `docs/taito-ku-data-report.md`.

**Sentinel values:**
- `measured_height = -9999` → no height measurement; filter with `measured_height > 0`
- `storeys_above_ground = 9999` → unknown; filter with `storeys_above_ground < 9999`
- `year_of_construction` → all NULL in Taito-ku 2024 (not surveyed)

## SQL Safety Rules

`database.py` enforces:
1. Only `SELECT` statements (rejects anything else with `QueryError`)
2. Auto-injects `LIMIT 1000` if no LIMIT is present
3. 30-second query timeout via `asyncio.wait_for`

## Documentation

- `docs/taito-ku-data-report.md` — **Start here.** Data statistics, attribute coverage, known limitations
- `docs/data-sources.md` — PLATEAU feature types, download URL, full codelists
- `docs/3dcitydb-v4-schema.md` — DB table reference and common query patterns
- `docs/architecture.md` — Full system design and data flow
- `docs/setup.md` — Installation and data import walkthrough
- `docs/query-examples.md` — Sample NL queries with verified SQL
- `docs/data-pipeline.md` — DB snapshot strategy, git tag history
