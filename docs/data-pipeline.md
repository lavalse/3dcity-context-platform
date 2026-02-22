# Data Pipeline & Version Management

## The Three-Layer Strategy

This project separates concerns into three layers, each managed differently:

```
┌─────────────────────────────────────────────────┐
│  Layer 1: Code (Git)                            │
│  backend/, frontend/, docs/, infra/, scripts/  │
│  docker-compose.yml, .env.example, CLAUDE.md   │
│  → Commit to git, tag releases                 │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Layer 2: DB Snapshots (Shared Storage)         │
│  pg_dump files (.dump) — NOT in git             │
│  → Store on team shared drive / S3 / etc.       │
│  → Document current snapshot in this file       │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Layer 3: Raw Data (PLATEAU official source)    │
│  CityGML files in data/citygml/ — .gitignored  │
│  → Always re-downloadable from PLATEAU portal   │
│  → URLs documented in docs/data-sources.md      │
└─────────────────────────────────────────────────┘
```

## DB Snapshot Log

Track DB snapshots here so the team knows which dump to use.

| Version | Date | Contents | File | Location |
|---|---|---|---|---|
| v0.2.0 | TBD | bldg (72,486 buildings), tran, luse, urf, fld | `taito-ku_3dcitydb_v0.2.0.dump` | TBD |
| v0.1.0 | 2026-02-22 | bldg only (72,486 buildings, LOD1+LOD2) | `taito-ku_3dcitydb_20260222_bldg.dump` | TBD |

**To create a new snapshot:**
```bash
./scripts/db-dump.sh taito-ku_3dcitydb_v0.1.0.dump
# Then upload to shared storage and update the table above
```

**To restore from a snapshot (new team member onboarding):**
```bash
docker compose up -d db     # Start DB container
./scripts/db-restore.sh ~/Downloads/taito-ku_3dcitydb_v0.1.0.dump
```

## Git Tag Strategy

| Tag | Contents |
|---|---|
| `v0.1.0` | Project scaffolding, docs, configs. Building data imported. |
| `v0.2.0` | All feature types imported (tran, luse, urf, fld). Attribute issue resolved. |
| `v0.3.0` | Backend MVP — NL-to-SQL working end-to-end. |
| `v0.4.0` | Frontend MVP — working prototype for city staff. |

## What's Stored Where

| Artifact | Storage | Notes |
|---|---|---|
| Application code | Git | `backend/`, `frontend/`, `infra/` |
| Documentation | Git | `docs/`, `CLAUDE.md`, `README.md` |
| Config templates | Git | `.env.example`, `docker-compose.yml` |
| Secrets | Local only | `.env` — never commit |
| CityGML source files | Local only | `data/citygml/` — .gitignored, re-download from PLATEAU |
| PostgreSQL DB volume | Local Docker | `pgdata` Docker volume |
| DB snapshots | Shared storage | `.dump` files — see log above |
| Import scripts | Git | `data/import/`, `scripts/` |

## Reproducing the Environment from Scratch

If you're joining the project or starting fresh:

**Option A — Fast (from DB snapshot):**
```bash
git clone <repo>
cd 3dcity-context-platform
cp .env.example .env
docker compose up -d db
./scripts/db-restore.sh ~/Downloads/taito-ku_3dcitydb_v0.1.0.dump
docker compose up -d
```

**Option B — Full pipeline (from raw CityGML):**
```bash
git clone <repo>
cd 3dcity-context-platform
cp .env.example .env
docker compose up -d db
# Download PLATEAU data (see docs/setup.md)
./data/import/run-import.sh ...  # see docs/setup.md for order
docker compose up -d
```

## Current Data State (as of 2026-02-22) — v0.2.0

### Imported ✓

| Feature | DB classname | Count | Notes |
|---|---|---|---|
| Buildings (bldg) | Building | 72,486 | LOD1+LOD2 with textures |
| Building surfaces | BuildingWallSurface etc. | 638,485 | Wall, roof, ground |
| Roads (tran) | Road | 22,172 | + 25,769 TrafficArea |
| Land use (luse) | LandUse | 188,273 | Full ward coverage |
| Flood zones (fld) | WaterBody | 1,740 | 3 river watersheds |

### Not imported / dropped

| Feature | Reason |
|---|---|
| Urban planning zones (urf) | PLATEAU ADE type — standard importer drops these (0 records) |
| uro: ADE attributes | buildingStructureType, detailedUsage, fireproofStructureType, floodRisk — dropped by importer |
| brid, frn, veg | Not yet imported (secondary priority) |

### Known Attribute Issues

1. **PLATEAU uses `bldg:usage` not `bldg:function`** — `building.usage` is populated (all 72,486 buildings). `building.function` is always NULL. See `docs/query-examples.md` for the correct usage codelist.

2. **`year_of_construction` not in this survey** — NULL for all buildings. Taito-ku 2024 PLATEAU data does not include construction year.

3. **Sentinel values**: `-9999` for height means no measurement; `9999` for floors means unknown. Always filter these out in queries.

4. **Flood zones as WaterBody**: The `fld` data imported as `WaterBody` objects (standard 3DCityDB type). Queryable via `classname = 'WaterBody'`.
