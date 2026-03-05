# 3D City Context Platform

A prototype that lets Tokyo Taito-ku (台東区) city staff ask natural language questions about the ward's 3D city model and get answers backed by real spatial database queries.

**Status:** Prototype / Research

## What It Does

The app has three tabs:

- **クエリ / Query** — Type a question; Claude generates SQL, shows it for review, executes it, and returns tabular results.
- **チャット / Chat** — Conversational interface powered by Claude's agentic tool-use loop. Claude autonomously runs one or more SQL queries, interprets results, and answers in Japanese. Multi-turn conversation with history.
- **地図 / Map** — MapLibre GL JS map with MVT building footprints and themed layers (land use, roads, flood zones). Click a building to see its attributes and 3D LOD2 surfaces.

Example questions:
- 台東区で10階以上のビルは何棟？
- 浸水区域と重なる住宅系の建物を教えて
- Show me buildings over 31 meters tall with their construction year.

## Stack

- **Database**: PostgreSQL 15 + PostGIS + [3DCityDB v4](https://github.com/3dcitydb/3dcitydb)
- **Data**: Tokyo Taito-ku 2024 PLATEAU CityGML (CC BY 4.0)
- **Backend**: Python 3.12 + FastAPI + asyncpg + Anthropic Claude API (claude-sonnet-4-6)
- **Tiles**: [Martin](https://github.com/maplibre/martin) MVT tile server
- **Frontend**: Plain HTML/CSS/JS + MapLibre GL JS + deck.gl (no build step)
- **Infrastructure**: Docker Compose

## Quick Start

See [docs/setup.md](docs/setup.md) for the full setup guide.

```bash
cp .env.example .env        # Set ANTHROPIC_API_KEY
docker compose up -d db     # Start 3DCityDB
# Download and import PLATEAU data (see docs/setup.md)
docker compose up -d        # Start full stack
open http://localhost:3000
```

## Backend API

| Endpoint | Description |
|---|---|
| `GET /api/health` | DB ping + LLM mode status |
| `POST /api/query` | Single-turn NL-to-SQL (placeholder or Claude) |
| `POST /api/chat` | Streaming SSE chat with agentic tool-use loop |
| `GET /api/buildings/{gmlid}` | Building attributes + LOD1/LOD2 geometry |

## Chat Endpoint — How It Works

`POST /api/chat` accepts a list of messages and streams [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events):

- Claude drives the conversation, calling `execute_sql` autonomously (up to 4 rounds)
- Auto-retries on empty results or SQL errors
- Final round streams Japanese natural-language interpretation token by token
- Events: `thinking`, `sql`, `executing`, `results`, `token`, `error`, `done`

Requires `ANTHROPIC_API_KEY` in `.env`.

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
