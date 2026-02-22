# 3D City Context Platform

A prototype that lets Tokyo Taito-ku (台東区) city staff ask natural language questions about the ward's 3D city model and get answers backed by real spatial database queries.

**Status:** Prototype / Research

## What It Does

City staff type a question in natural language (Japanese or English). The system generates SQL using Claude AI, shows the user the SQL for review, executes it against a 3DCityDB database loaded with Taito-ku PLATEAU CityGML data, and returns results.

Example questions:
- 台東区で1981年以前に建てられた木造建物は何棟ありますか？
- How many buildings are in flood hazard zones along the Sumida River?
- Show me buildings over 31 meters tall with their construction year.

## Stack

- **Database**: PostgreSQL 15 + PostGIS + [3DCityDB v4](https://github.com/3dcitydb/3dcitydb)
- **Data**: Tokyo Taito-ku 2024 PLATEAU CityGML (CC BY 4.0)
- **Backend**: Python 3.12 + FastAPI + asyncpg + Anthropic Claude API
- **Frontend**: Plain HTML/CSS/JS (no build step)
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

## Documentation

| Doc | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | System design, data flow, technical decisions |
| [docs/data-sources.md](docs/data-sources.md) | PLATEAU Taito-ku data: feature types, attributes, codelists |
| [docs/3dcitydb-v4-schema.md](docs/3dcitydb-v4-schema.md) | Key DB tables, columns, query patterns |
| [docs/setup.md](docs/setup.md) | Installation, data import, troubleshooting |
| [docs/query-examples.md](docs/query-examples.md) | Sample NL queries and their SQL |

## License

Application code: MIT
PLATEAU data: CC BY 4.0 (Ministry of Land, Infrastructure, Transport and Tourism, Japan)
