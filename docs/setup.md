# Setup Guide

## Resuming After a Break

If you have already completed the initial setup and just want to continue working:

```bash
cd /home/red/projects/3dcity-context-platform
docker compose up -d
```

That's it. The database data is persisted in a Docker volume and survives restarts. Check everything is running:

```bash
curl http://localhost:3000/api/health
# Expected: {"status":"ok","db":"connected","llm_mode":"claude_api"}
```

Then open **http://localhost:3000** in the browser.

If the backend shows `"llm_mode":"placeholder"` after resuming, your `ANTHROPIC_API_KEY` in `.env` may have been cleared — re-add it and run:

```bash
docker compose up -d --force-recreate backend
```

---

## Prerequisites (First-Time Setup Only)

- Docker Desktop (or Docker Engine + Compose plugin)
- 10+ GB free disk space (CityGML data + PostgreSQL)
- Python 3.12+ (for local backend development, optional if using Docker)
- An Anthropic API key (for Claude NL-to-SQL)

## 1. Environment Configuration

```bash
cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY
```

## 2. Start the Database

```bash
docker compose up -d db
docker compose logs -f db  # Wait until "database system is ready to accept connections"
```

The 3DCityDB v4 schema is initialized automatically by the Docker image on first run (using SRID=6668 for JGD2011 geographic 2D, matching PLATEAU CityGML).

Verify the DB is ready:
```bash
docker exec 3dcitydb-pg psql -U citydb -d citydb -c "\dt citydb.*" | head -20
```

You should see tables: `building`, `cityobject`, `objectclass`, `surface_geometry`, etc.

## 3. Download PLATEAU Taito-ku Data

```bash
mkdir -p data/citygml
cd data/citygml

# Full CityGML package (all feature types, ~1-2 GB)
wget "https://s3.tlab.cloud/spatialid/tokyo23ku/dl/13106_taito-ku_city_2024_citygml_1_op.zip"
unzip 13106_taito-ku_city_2024_citygml_1_op.zip
cd ../..
```

After unzipping, the directory structure will look like:
```
data/citygml/13106_taito-ku_city_2024_citygml_1_op/
└── udx/
    ├── bldg/       # Building GML files (split by mesh code)
    ├── tran/       # Road GML files
    ├── luse/       # Land use GML files
    ├── fld/        # River flood hazard GML files
    ├── htd/        # High-tide (storm surge) flood hazard GML files
    ├── brid/       # Bridge GML files
    ├── dem/        # DEM elevation TIN files
    ├── frn/        # City furniture GML files
    ├── veg/        # Vegetation GML files
    ├── urf/        # Urban planning zones (PLATEAU ADE — not importable)
    ├── lsld/       # Landslide hazard zones (PLATEAU ADE — not importable)
    └── ...
```

## 4. Import Data into 3DCityDB

Import all standard CityGML feature types in the order shown. The importer processes a directory recursively.

```bash
# Import buildings (largest dataset, may take 10-30 minutes)
./data/import/run-import.sh udx/bldg

# Import roads
./data/import/run-import.sh udx/tran

# Import land use
./data/import/run-import.sh udx/luse

# Import river flood hazard zones
./data/import/run-import.sh udx/fld

# Import high-tide (storm surge) flood hazard zones
./data/import/run-import.sh udx/htd

# Import bridges
./data/import/run-import.sh udx/brid

# Import DEM elevation data
./data/import/run-import.sh udx/dem

# Import city furniture (street poles, signs, lights)
./data/import/run-import.sh udx/frn

# Import vegetation
./data/import/run-import.sh udx/veg
```

**Note:** Do NOT import `udx/urf` or `udx/lsld` — these are PLATEAU ADE types that the standard 3DCityDB importer does not support (0 records would be imported).

Verify the import was complete:
```bash
./data/import/verify-import.sh
# Expected: all 8 feature types PASS
```

## 5. Create Materialized Views for Map Tiles

The map requires materialized views that transform 3DCityDB data into tile-ready format (EPSG:4326 WGS84) for the Martin tile server.

```bash
# Create building footprints view (~30-90 seconds for 90k buildings)
docker exec -i 3dcitydb-pg psql -U citydb -d citydb < data/migrations/001_building_footprints_mv.sql

# Create land use, road, and flood zone views
docker exec -i 3dcitydb-pg psql -U citydb -d citydb < data/migrations/002_additional_layers_mv.sql

# Create bridge, city furniture, and vegetation views; refresh flood zones to include htd
docker exec -i 3dcitydb-pg psql -U citydb -d citydb < data/migrations/003_new_layers_mv.sql
```

**Note:** `003_new_layers_mv.sql` also runs `REFRESH MATERIALIZED VIEW citydb.flood_zone_footprints`,
which makes the high-tide flood zone (htd, 7,021 objects) appear on the map alongside the river
flood zone (fld, 1,740 objects) — no separate step needed.

Verify the views were created:
```bash
docker exec 3dcitydb-pg psql -U citydb -d citydb -c "
SELECT schemaname, matviewname
FROM pg_matviews
WHERE schemaname = 'citydb'
ORDER BY matviewname;"
```

Expected output:
```
 schemaname |      matviewname
------------+-----------------------
 citydb     | bridge_footprints
 citydb     | building_footprints
 citydb     | flood_zone_footprints
 citydb     | furniture_footprints
 citydb     | land_use_footprints
 citydb     | road_footprints
 citydb     | vegetation_footprints
```

**Note:** Without these views, the map will appear blank (no buildings visible).

## 6. Start the Full Stack

```bash
docker compose up -d
```

Services:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- DB: localhost:5432

## 7. Local Backend Development (Optional)

For faster iteration without rebuilding the Docker image:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run with auto-reload (DB must be running in Docker)
uvicorn app.main:app --reload --port 8000
```

## Troubleshooting

### DB container fails to start

Check if port 5432 is already in use:
```bash
lsof -i :5432
```

Change `POSTGRES_PORT` in `.env` if needed.

### Import fails with connection error

The import script uses `--network host` to connect to `localhost:5432`. If you changed the port, edit `data/import/run-import.sh` accordingly.

### `citydb.*` tables don't exist after DB starts

The 3DCityDB Docker image initializes the schema using the SRID and HEIGHT_EPSG environment variables on first start. If the volume already existed with a different SRID, delete the volume and restart:

```bash
docker compose down -v  # WARNING: deletes all data
docker compose up -d db
```

### SRID mismatch errors during import

PLATEAU CityGML uses JGD2011 (EPSG:6697 for 3D, EPSG:6668 for 2D). The DB is initialized with SRID=6668. The importer should handle CRS transformations automatically. If not, check the importer log output.
