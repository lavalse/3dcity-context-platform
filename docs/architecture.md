# Architecture

## Goal

A prototype that lets Tokyo Taito-ku city staff ask natural language questions about the ward's 3D city model data and get answers backed by real spatial database queries. The system is designed to be transparent: the generated SQL is always shown to the user before execution.

## System Overview

```
City Staff (Japanese / English)
          │
          │  natural language question / map interaction
          ▼
┌─────────────────────────────────────────────────────────┐
│                   Frontend (Browser)                    │
│  Query tab: NL input → SQL review → tabular results    │
│             results highlighted on map (table-map sync) │
│  Chat tab:  conversational, streaming SSE               │
│  Map tab:   MVT tiles (MapLibre) + Cesium 3D LOD2      │
│             multi-feature selection, export, CRUD edit  │
└────────────────────┬────────────────────────────────────┘
                     │  HTTP  /api/*
                     ▼
┌─────────────────────────────────────────────────────────┐
│                FastAPI Backend (Python)                 │
│                                                         │
│  NL-to-SQL: schema context → Claude API → SQL           │
│  Chat: agentic tool-use loop (up to 4 SQL rounds)      │
│  Buildings read: attrs + LOD1/LOD2 geometry + export   │
│  Buildings write: PATCH / DELETE / PUT lod1 / PUT lod2 │
│  Export: GeoJSON FeatureCollection (mixed types)       │
└──────┬─────────────────────────────────┬────────────────┘
       │  asyncpg (SELECT)               │  asyncpg (write)
       ▼                                 ▼
┌─────────────────────────────────────────────────────────┐
│       PostgreSQL 15 + PostGIS + 3DCityDB v4             │
│                                                         │
│  Schema: citydb                                         │
│  Data: Taito-ku 2024 PLATEAU CityGML                   │
│  Feature types: bldg, tran, luse, fld                  │
│  CRS: JGD2011 geographic 2D (EPSG:6668)                │
└───────────────────────────┬─────────────────────────────┘
                            │  auto-discover tables
                            ▼
                  ┌──────────────────┐
                  │  Martin (MVT)    │
                  │  tile cache: OFF │
                  │  /tiles/*        │
                  └──────────────────┘
```

## Component Responsibilities

### Backend (`backend/app/`)

| Module | Purpose |
|---|---|
| `main.py` | FastAPI app setup, CORS (GET/POST/PATCH/PUT/DELETE), route mounting |
| `config.py` | Settings from environment variables; `use_llm` checks key format |
| `database.py` | asyncpg connection pool; `run_query()` — SELECT-only, auto-LIMIT 1000, 30s timeout |
| `database_write.py` | Write utilities: `execute_write`, `execute_transaction`, `refresh_mv` |
| `api/query.py` | `POST /api/query` — single-turn NL-to-SQL |
| `api/chat.py` | `POST /api/chat` — streaming SSE agentic chat |
| `api/health.py` | `GET /api/health` — DB ping + LLM mode |
| `api/buildings.py` | Read endpoints: search, detail, LOD2 export (GeoJSON 3D / CityJSON), batch export |
| `api/buildings_write.py` | Write endpoints: PATCH attrs, DELETE, PUT lod1, PUT lod2 |
| `api/export.py` | `POST /api/export` — GeoJSON FeatureCollection for mixed feature types |
| `api/features.py` | `GET /api/features/{gmlid}` — non-building feature attributes |
| `services/sql_generator.py` | Two-mode SQL generator: Claude API or keyword placeholder |
| `services/schema_context.py` | Loads `system_prompt.md` for LLM context |
| `prompts/system_prompt.md` | Schema, codelists, SQL rules for NL-to-SQL |
| `prompts/chat_system_prompt.md` | System prompt + `execute_sql` tool definition for chat |

### Frontend (`frontend/`)

Single-page HTML application, no build step required. Served by nginx in Docker.

| Tab | Key libraries | Features |
|---|---|---|
| Query | — | NL input, SQL review, results table, map highlight sync |
| Chat | — | SSE streaming, multi-turn history, token-by-token display |
| Map | MapLibre GL JS, deck.gl, Cesium | MVT tiles, Cesium 3D LOD2, box/polygon multi-select, GeoJSON/CityJSON export, CRUD edit panel |

### Infrastructure (`infra/`)

- `infra/nginx/nginx.conf` — Reverse proxy: `/api/*` → backend:8000, `/tiles/*` → martin:3000, static frontend

### Data (`data/`)

- `data/citygml/` — Downloaded PLATEAU CityGML files (not committed)
- `data/import/run-import.sh` — Runs `3dcitydb/impexp` Docker image to load GML into DB
- `data/migrations/001_building_footprints_mv.sql` — Creates `citydb.building_footprints` table (initially as MV, later converted to a regular table for synchronous write support)
- `data/migrations/002_building_footprints_table.sql` — Converts MV to regular table, enables real-time tile updates after LOD1 edits

### Martin (MVT tile server)

Martin auto-discovers `citydb.building_footprints` and serves it as vector tiles at `/tiles/building_footprints/{z}/{x}/{y}.pbf`.

**Tile cache is disabled** (`-C 0` flag) so that LOD1 geometry edits are reflected immediately in the next tile request — no cache invalidation needed.

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

### Read/Write DB Path Separation

The read path (`database.py::run_query`) enforces SELECT-only and auto-injects LIMIT. The write path (`database_write.py`) is a separate module with explicit transaction support — this keeps the safety guarantees of the read path intact.

### Synchronous Tile Updates

Early versions used a `MATERIALIZED VIEW` for building footprints and triggered `REFRESH MATERIALIZED VIEW CONCURRENTLY` asynchronously after writes. This caused 3–5 s stale tiles. The current design:

1. `building_footprints` is a **regular table** (migration 002) — rows are updated synchronously before the HTTP response is returned.
2. Martin's in-memory tile cache is **disabled** (`-C 0`) — every tile request hits the DB directly.
3. The frontend calls `refreshMapTiles()` immediately after a save/delete response (no `setTimeout` delay).

### PLATEAU-Specific Challenges

1. **Codelists**: `bldg:usage` codes like `'411'` mean "住宅 (detached house)" — the LLM must know these mappings.
2. **uro: ADE attributes**: PLATEAU's urban planning attributes were dropped during import (`cityobject_genericattrib` is empty in Taito-ku 2024).
3. **Geometry CRS**: All geometries are in JGD2011 (EPSG:6668, lat/lon order). API responses flip coordinates to lon/lat for GeoJSON.

## Data Flow: Query Lifecycle

```
1. User types: "台東区で10階以上のビルは何棟？"

2. Schema context builder injects:
   - BUILDING table description (measured_height, storeys_above_ground, usage, etc.)
   - PLATEAU codelist values
   - Few-shot SQL examples

3. Claude API returns SQL + explanation.

4. SQL displayed to user for review (editable).

5. asyncpg executes against PostgreSQL (SELECT-only, 30s timeout).

6. Results returned as {"columns": [...], "rows": [...], "count": N}

7. Frontend renders table + highlights matching buildings on map.
   Clicking a row pans the map; clicking a tile feature selects its row.
```

## Data Flow: LOD1 Edit Lifecycle

```
1. User draws new footprint polygon on map, enters height.

2. PUT /api/buildings/{gmlid}/lod1
   - Deletes old surface_geometry rows
   - Inserts new solid geometry (WKT, EPSG:6668)
   - Updates building_footprints table row synchronously

3. HTTP 200 returned.

4. Frontend calls refreshMapTiles() immediately:
   src.setTiles([BUILDINGS_TILE_URL + '?_t=' + Date.now()])
   → Martin fetches fresh tile from DB (no cache)
   → Updated footprint visible within ~1s
```
