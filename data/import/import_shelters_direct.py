#!/usr/bin/env python3
"""Import PLATEAU shelter GeoJSON into citydb.shelter_facilities.
Usage: python import_shelters_direct.py [path-or-url]
"""
import asyncio
import json
import sys
import urllib.request

import asyncpg

SOURCE = sys.argv[1] if len(sys.argv) > 1 else \
    "https://assets.cms.plateau.reearth.io/assets/c9/6d984f-6d29-4ecb-9442-ec8baaff4566/13106_tokyo23ku-taito-ku_pref_2023_shelter.geojson"
DSN = "postgresql://citydb:citydb@3dcitydb-pg:5432/citydb"


def load_geojson(src):
    if src.startswith("http"):
        with urllib.request.urlopen(src) as r:
            return json.loads(r.read())
    with open(src, encoding="utf-8") as f:
        return json.load(f)


def parse_feature(feat):
    p = feat.get("properties", {})
    c = feat.get("geometry", {}).get("coordinates")
    if not c:
        return None
    # Convert numeric fields safely
    def to_int(v):
        try:
            return int(v) if v is not None else None
        except (ValueError, TypeError):
            return None

    def to_float(v):
        try:
            return float(v) if v is not None else None
        except (ValueError, TypeError):
            return None

    return (
        p.get("名称"),
        p.get("住所"),
        to_int(p.get("レベル")),
        to_int(p.get("収容人数")),
        p.get("対象とする災害の分類"),
        p.get("施設の種類"),
        to_float(p.get("施設規模")),
        p.get("行政区域"),
        to_float(p.get("高さ")),
        float(c[0]),
        float(c[1]),
    )


async def main():
    print(f"Loading {SOURCE} ...")
    fc = load_geojson(SOURCE)
    rows = [r for f in fc["features"] if (r := parse_feature(f))]
    print(f"  → {len(rows)} features")

    print(f"Connecting to {DSN} ...")
    conn = await asyncpg.connect(DSN)

    print("Creating table citydb.shelter_facilities ...")
    await conn.execute("DROP TABLE IF EXISTS citydb.shelter_facilities CASCADE")
    await conn.execute("""
        CREATE TABLE citydb.shelter_facilities (
            id             serial PRIMARY KEY,
            name           varchar(200),
            address        varchar(300),
            level          integer,
            capacity       integer,
            disaster_types varchar(500),
            facility_type  varchar(200),
            facility_area  numeric(12,2),
            district       varchar(200),
            height         numeric(8,2),
            geometry       geometry(Point, 4326)
        )
    """)

    print(f"Inserting {len(rows)} rows ...")
    await conn.executemany(
        "INSERT INTO citydb.shelter_facilities "
        "(name, address, level, capacity, disaster_types, facility_type, facility_area, district, height, geometry) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9, ST_SetSRID(ST_MakePoint($10,$11), 4326))",
        rows,
    )

    await conn.execute("CREATE INDEX ON citydb.shelter_facilities USING GIST (geometry)")
    await conn.execute("CREATE INDEX ON citydb.shelter_facilities (level)")

    count = await conn.fetchval("SELECT COUNT(*) FROM citydb.shelter_facilities")
    sample = await conn.fetch(
        "SELECT id, name, level FROM citydb.shelter_facilities ORDER BY id LIMIT 5"
    )
    await conn.close()

    print(f"\nDone! {count} rows in citydb.shelter_facilities")
    print("Sample rows:")
    for r in sample:
        print(f"  id={r['id']}  level={r['level']}  {r['name']}")


asyncio.run(main())
