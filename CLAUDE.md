# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Prototype NL-to-SQL application for Tokyo Taito-ku (台東区) city staff to query 3D city model data. City staff type natural language questions; the system generates SQL via Claude API, shows it for review, then executes it against a 3DCityDB v4 PostgreSQL database loaded with PLATEAU CityGML data.

## Commands

### Start / Stop

```bash
docker compose up -d          # Start all services (db + backend + frontend)
docker compose up -d db       # Start only the database
docker compose logs -f        # Stream all logs
docker compose down           # Stop all services (data preserved)
docker compose down -v        # Stop and delete all data volumes
```

### Backend development (local, faster iteration)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Database access

```bash
docker exec -it 3dcitydb-pg psql -U citydb -d citydb
```

### Import PLATEAU CityGML data

```bash
# After downloading and unzipping PLATEAU data to data/citygml/
./data/import/run-import.sh 13106_taito-ku_city_2024_citygml_1_op/udx/bldg
./data/import/run-import.sh 13106_taito-ku_city_2024_citygml_1_op/udx/tran
./data/import/run-import.sh 13106_taito-ku_city_2024_citygml_1_op/udx/luse
./data/import/run-import.sh 13106_taito-ku_city_2024_citygml_1_op/udx/urf
./data/import/run-import.sh 13106_taito-ku_city_2024_citygml_1_op/udx/fld
```

### Verify data import

```bash
docker exec 3dcitydb-pg psql -U citydb -d citydb -c "
SELECT oc.classname, COUNT(*) FROM citydb.cityobject co
JOIN citydb.objectclass oc ON oc.id = co.objectclass_id
GROUP BY oc.classname ORDER BY count DESC;"
```

## Architecture

```
frontend/ (HTML/JS) → nginx :3000
    → /api/* proxy → backend/ (FastAPI) :8000
        → Anthropic Claude API (NL → SQL generation)
        → asyncpg → PostgreSQL :5432 (3DCityDB v4 schema)
```

**Key design decision: 3DCityDB v4, not v5.** PLATEAU data is CityGML 2.0. v4 maps it to explicit readable columns (`measured_height`, `storeys_above_ground`, `year_of_construction`). v5's generic `PROPERTY` table would make LLM-generated SQL hard to produce correctly.

## Backend Module Map

| File | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app, CORS, route mounting |
| `backend/app/config.py` | Settings via pydantic-settings / env vars |
| `backend/app/database.py` | asyncpg pool, safe query execution (read-only, 30s timeout, auto-LIMIT) |
| `backend/app/api/query.py` | `POST /api/query` — main endpoint |
| `backend/app/api/health.py` | `GET /api/health` |
| `backend/app/services/sql_generator.py` | Calls Claude API with schema context; returns SQL + explanation |
| `backend/app/services/sql_runner.py` | Validates SQL (SELECT only), injects LIMIT, executes |
| `backend/app/services/schema_context.py` | Builds LLM prompt from schema docs + codelists |
| `backend/app/prompts/` | Schema descriptions and few-shot examples (Markdown files) |

## Database Schema

All tables in the `citydb` PostgreSQL schema. Key tables:

- `citydb.cityobject` — All city features; `gmlid` is the CityGML identifier
- `citydb.building` — Building attributes: `measured_height`, `storeys_above_ground`, `year_of_construction`, `function`, `roof_type`
- `citydb.cityobject_genericattrib` — PLATEAU `uro:` ADE attributes stored as key-value; query by `attrname` (e.g., `'uro:buildingStructureType'`)
- `citydb.surface_geometry` — Geometry storage; join via `lod1_solid_id` / `lod2_solid_id` in `building`
- `citydb.address` / `citydb.address_to_building` — Address data

Always filter with `WHERE building_root_id = id` to exclude BuildingParts (sub-components that share geometry).

Coordinate system: EPSG:6668 (JGD2011 geographic 2D). Use this SRID in PostGIS functions.

## Key PLATEAU Codelists

**Building function** (`building.function`):
- `'0401'` = 専用住宅 (detached house)
- `'0402'` = 共同住宅 (apartment)
- `'0507'` = 商業・業務施設 (commercial)

**Structure type** (`cityobject_genericattrib` where `attrname = 'uro:buildingStructureType'`):
- `'601'` = 木造 (wood)
- `'603'` = RC造 (reinforced concrete)
- `'604'` = 鉄骨造 (steel frame)

Full codelists in `docs/data-sources.md`.

## SQL Safety Rules

The SQL runner must enforce:
1. Only `SELECT` statements allowed
2. Auto-inject `LIMIT 1000` if no LIMIT present
3. 30-second query timeout
4. Use a read-only PostgreSQL role (no INSERT/UPDATE/DELETE privileges)

## Documentation

- `docs/architecture.md` — Full system design and data flow
- `docs/data-sources.md` — PLATEAU data types, download URL, all codelists
- `docs/3dcitydb-v4-schema.md` — DB table reference and query patterns
- `docs/setup.md` — Installation and data import
- `docs/query-examples.md` — Sample NL queries with SQL (use as few-shot examples)
