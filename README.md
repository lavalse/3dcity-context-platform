# 3D City Context Platform

A prototype that lets Tokyo Taito-ku (台東区) city staff ask natural language questions about the ward's 3D city model and get answers backed by real spatial database queries.

**Status:** Prototype / Research

## What It Does

The app has three tabs:

- **クエリ / Query** — Type a question; Claude generates SQL, shows it for review, executes it, and returns tabular results. Query results are highlighted on the map in sync with the table — click a row to pan to the building, click a building to select its row.
- **チャット / Chat** — Conversational interface powered by Claude's agentic tool-use loop. Claude autonomously runs one or more SQL queries, interprets results, and answers in Japanese. Multi-turn conversation with history.
- **地図 / Map** — Full interactive map with MVT building footprints and themed layers (land use, roads, flood zones). Features:
  - Click any feature (building, road, land use, flood zone) to see its attributes
  - Switch to **Cesium 3D** view for LOD2 surface rendering
  - **Multi-selection**: box-draw or polygon-draw to select multiple buildings
  - **Export**: download selected features as GeoJSON (2D), GeoJSON 3D (LOD2 extrusions), or CityJSON
  - **CRUD edit panel**: edit building attributes, replace LOD1/LOD2 geometry, delete buildings

Example questions:
- 台東区で10階以上のビルは何棟？
- 浸水区域と重なる住宅系の建物を教えて
- Show me buildings over 31 meters tall with their construction year.

## Stack

- **Database**: PostgreSQL 15 + PostGIS + [3DCityDB v4](https://github.com/3dcitydb/3dcitydb)
- **Data**: Tokyo Taito-ku 2024 PLATEAU CityGML (CC BY 4.0)
- **Backend**: Python 3.12 + FastAPI + asyncpg + Anthropic Claude API (claude-sonnet-4-6)
- **Tiles**: [Martin](https://github.com/maplibre/martin) MVT tile server (tile cache disabled for real-time updates)
- **Frontend**: Plain HTML/CSS/JS + MapLibre GL JS + deck.gl + Cesium (no build step)
- **Infrastructure**: Docker Compose

## Quick Start

See [docs/setup.md](docs/setup.md) for the full setup guide.

```bash
cp .env.example .env        # Set ANTHROPIC_API_KEY
docker compose up -d db     # Start 3DCityDB
# Download and import PLATEAU data (see docs/setup.md)
# Run migrations to create tile tables (see docs/setup.md step 5)
docker compose up -d        # Start full stack
open http://localhost:3000
```

## Backend API

### Query & Chat

| Endpoint | Description |
|---|---|
| `GET /api/health` | DB ping + LLM mode status |
| `POST /api/query` | Single-turn NL-to-SQL (placeholder or Claude) |
| `POST /api/chat` | Streaming SSE chat with agentic tool-use loop |

### Buildings (Read)

| Endpoint | Description |
|---|---|
| `GET /api/buildings/search` | Search buildings by name/gmlid prefix |
| `GET /api/buildings/{gmlid}` | Building attributes + LOD1/LOD2 geometry |
| `GET /api/buildings/{gmlid}/export/geojson3d` | LOD2 surfaces as GeoJSON 3D |
| `GET /api/buildings/{gmlid}/export/cityjson` | LOD2 surfaces as CityJSON |
| `POST /api/buildings/export/batch` | Batch LOD2 export for box-selected buildings |

### Buildings (Write)

| Endpoint | Description |
|---|---|
| `PATCH /api/buildings/{gmlid}` | Update name / usage / height / storeys |
| `DELETE /api/buildings/{gmlid}` | Cascade-delete building and all its geometry |
| `PUT /api/buildings/{gmlid}/lod1` | Replace LOD1 solid from GeoJSON Polygon + height |
| `PUT /api/buildings/{gmlid}/lod2` | Replace LOD2 thematic surfaces from GeoJSON |

### Export

| Endpoint | Description |
|---|---|
| `POST /api/export` | GeoJSON FeatureCollection for mixed feature types (buildings, roads, land use, flood zones) |

### Features

| Endpoint | Description |
|---|---|
| `GET /api/features/{gmlid}` | Attributes for any non-building feature (road, land use, flood zone) |

## Chat Endpoint — How It Works

`POST /api/chat` accepts a list of messages and streams [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events):

- Claude drives the conversation, calling `execute_sql` autonomously (up to 4 rounds)
- Auto-retries on empty results or SQL errors
- Final round streams Japanese natural-language interpretation token by token
- Events: `thinking`, `sql`, `executing`, `results`, `token`, `error`, `done`

Requires `ANTHROPIC_API_KEY` in `.env`.

## Coordinate Reference Systems

This project touches several CRS layers. Getting axis order wrong causes geometries to appear in the ocean.

### CRS Chain

| Layer | EPSG | Name | Axis Order |
|---|---|---|---|
| PLATEAU CityGML source | 6697 | JGD2011 geographic 3D | lat, lon, height (deg/deg/m) |
| PLATEAU 3D Tiles (official) | 4978 | WGS84 geocentric ECEF | X, Y, Z (meters) |
| 3DCityDB v4 storage | 6668 | JGD2011 geographic 2D | **lat, lon** (Y, X) |
| Martin MVT tiles | 4326 | WGS84 geographic 2D | lon, lat |
| API GeoJSON output | 4326 | WGS84 geographic 2D | lon, lat |
| API GeoJSON write input | 4326 | WGS84 (GeoJSON standard) | lon, lat |
| CityJSON export | 6677 | JGD2011 Japan Plane CS IX | X, Y (meters) |

### Key Notes

**EPSG:6668 axis pitfall** — 3DCityDB stores all geometries in EPSG:6668 (JGD2011 geographic 2D), which uses **(latitude, longitude)** — opposite of GeoJSON. PostGIS stores coordinates literally as (lat, lon), i.e. (Y, X). All read paths apply `ST_FlipCoordinates()` to convert to standard (lon, lat) before returning GeoJSON.

**JGD2011 ≈ WGS84** — The two datums differ by <1 m in Japan. This project treats them as interchangeable for display purposes; no datum transformation is applied, only axis-order correction.

**MVT materialized views** — Created via `ST_SetSRID(ST_FlipCoordinates(geom), 4326)` to go from stored (lat, lon) EPSG:6668 to standard (lon, lat) EPSG:4326 for Martin.

**LOD1/LOD2 write endpoints** — Frontend sends `[lon, lat]` GeoJSON; `buildings_write.py` swaps to `(lat, lon)` before inserting as `ST_GeomFromText(..., 6668)`.

**CityJSON export transform** — Cannot transform directly from EPSG:6668 to EPSG:6677 due to a PROJ axis-order issue. Workaround: `ST_Transform(ST_SetSRID(ST_FlipCoordinates(geom), 4326), 6677)`.

### Known Pitfalls

| Problem | Cause | Fix |
|---|---|---|
| Geometries appear in the ocean | JGD2011 axis order is (lat, lon) | `ST_FlipCoordinates()` before returning GeoJSON |
| `ST_Transform(geom, 6677)` fails | PROJ axis-order issue with EPSG:6668 | Route through 4326: `ST_Transform(ST_SetSRID(ST_FlipCoordinates(geom), 4326), 6677)` |
| Bbox queries return wrong results | Envelope stored in (lat, lon) order | Use `ST_MakeEnvelope(lon_min, lat_min, lon_max, lat_max, 6668)` — PostGIS bbox overlap ignores axis order |

## Documentation

| Doc | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | System design, data flow, technical decisions |
| [docs/data-sources.md](docs/data-sources.md) | PLATEAU Taito-ku data: feature types, attributes, codelists |
| [docs/3dcitydb-v4-schema.md](docs/3dcitydb-v4-schema.md) | Key DB tables, columns, query patterns |
| [docs/setup.md](docs/setup.md) | Installation, data import, troubleshooting |
| [docs/query-examples.md](docs/query-examples.md) | Sample NL queries and their SQL |
| [docs/taito-ku-data-report.md](docs/taito-ku-data-report.md) | Data statistics, attribute coverage, known limitations |

## pgAdmin

http://localhost:5050 — email: `admin@citydb.local` / password: `admin`
Server connection password: `citydb`

## License

Application code: MIT
PLATEAU data: CC BY 4.0 (Ministry of Land, Infrastructure, Transport and Tourism, Japan)
