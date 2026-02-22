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

## Current Data State (as of 2026-02-22)

### Imported ✓
- **bldg** (buildings): 72,486 buildings, LOD1 + LOD2 with textures
  - Height: populated (median 10.3m, -9999 = no measurement)
  - Floors: populated (`storeys_above_ground`)
  - Function/year: stored as generic attributes (ADE namespace) — see known issues

### Not yet imported
- tran (roads)
- luse (land use)
- urf (urban planning zones)
- fld (flood hazard zones)
- brid, frn, veg (secondary)

### Known Issues
1. **`bldg:function` and `year_of_construction` are NULL** in the `building` table.
   PLATEAU stores these in the `uro:` ADE namespace. The importer may store them
   as generic attributes under different names. Run this to check:
   ```sql
   SELECT attrname, strval, intval
   FROM citydb.cityobject_genericattrib
   WHERE cityobject_id = (SELECT id FROM citydb.building LIMIT 1);
   ```

2. **Height sentinel value**: `-9999` means "height measurement failed". Always filter
   with `WHERE measured_height > 0` for height analysis queries.
