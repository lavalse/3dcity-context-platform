#!/usr/bin/env python3
"""
Import e-stat 小地域 GML directly into PostgreSQL without ogr2ogr.
Usage: python import_census_direct.py <path-to-gml>
Requires: asyncpg (already installed in backend container)
"""
import asyncio
import sys
import xml.etree.ElementTree as ET

import asyncpg

GML_FILE = sys.argv[1] if len(sys.argv) > 1 else "/data/r2ka13106.gml"
DSN = "postgresql://citydb:citydb@3dcitydb-pg:5432/citydb"

GML_NS  = "http://www.opengis.net/gml"
FME_NS  = "http://www.safe.com/gml/fme"


def parse_poslist(text: str) -> list[tuple[float, float]]:
    """'lat lon lat lon ...' (EPSG:6668) → list of (lon, lat) for EPSG:4326."""
    nums = list(map(float, text.split()))
    return [(nums[i + 1], nums[i]) for i in range(0, len(nums) - 1, 2)]


def ring_wkt(coords: list[tuple[float, float]]) -> str:
    return "(" + ", ".join(f"{lon} {lat}" for lon, lat in coords) + ")"


def patch_to_polygon_wkt(patch_el) -> str | None:
    ext = patch_el.find(f"{{{GML_NS}}}exterior/{{{GML_NS}}}LinearRing/{{{GML_NS}}}posList")
    if ext is None or not ext.text:
        return None
    rings = [ring_wkt(parse_poslist(ext.text))]
    for intr in patch_el.findall(f"{{{GML_NS}}}interior/{{{GML_NS}}}LinearRing/{{{GML_NS}}}posList"):
        if intr.text:
            rings.append(ring_wkt(parse_poslist(intr.text)))
    return "POLYGON(" + ", ".join(rings) + ")"


def parse_feature(feat_el) -> tuple | None:
    def get(tag: str) -> str | None:
        el = feat_el.find(f"{{{FME_NS}}}{tag}")
        return el.text.strip() if el is not None and el.text else None

    key_code = get("KEY_CODE")
    if not key_code:
        return None

    patches = feat_el.findall(f".//{{{GML_NS}}}PolygonPatch")
    polygons = [p for p in (patch_to_polygon_wkt(p) for p in patches) if p]
    if not polygons:
        return None

    # Build MULTIPOLYGON WKT
    # POLYGON((ring),(hole)) → MULTIPOLYGON(((ring),(hole)), ...)
    # poly_wkt[len("POLYGON"):] already gives "((ring),(hole))" — use directly
    inner_parts = [poly_wkt[len("POLYGON"):].strip() for poly_wkt in polygons]
    geom_wkt = "MULTIPOLYGON(" + ", ".join(inner_parts) + ")"

    return (
        key_code,
        get("PREF"),
        get("CITY"),
        get("S_AREA"),
        get("S_NAME"),   # neighborhood name — e-stat calls this S_NAME
        get("KCODE1"),
        geom_wkt,
    )


async def main():
    print(f"Parsing {GML_FILE} ...")
    tree = ET.parse(GML_FILE)
    root = tree.getroot()

    rows = []
    for fm in root.findall(f"{{{GML_NS}}}featureMember"):
        for feat_el in fm:
            row = parse_feature(feat_el)
            if row:
                rows.append(row)

    print(f"  → {len(rows)} features parsed")

    print(f"Connecting to {DSN} ...")
    conn = await asyncpg.connect(DSN)

    print("Creating table citydb.census_boundaries ...")
    await conn.execute("DROP TABLE IF EXISTS citydb.census_boundaries CASCADE")
    await conn.execute("""
        CREATE TABLE citydb.census_boundaries (
            key_code  varchar(20) PRIMARY KEY,
            pref      varchar(2),
            city      varchar(3),
            s_area    varchar(7),
            moji      varchar(40),
            kcode1    varchar(10),
            geometry  geometry(MultiPolygon, 4326)
        )
    """)

    print(f"Inserting {len(rows)} rows ...")
    await conn.executemany(
        """
        INSERT INTO citydb.census_boundaries (key_code, pref, city, s_area, moji, kcode1, geometry)
        VALUES ($1, $2, $3, $4, $5, $6, ST_GeomFromText($7, 4326))
        """,
        rows,
    )

    await conn.execute("CREATE INDEX ON citydb.census_boundaries USING GIST (geometry)")
    await conn.execute("CREATE INDEX ON citydb.census_boundaries (moji)")

    count = await conn.fetchval("SELECT COUNT(*) FROM citydb.census_boundaries")
    sample = await conn.fetch("SELECT key_code, moji FROM citydb.census_boundaries ORDER BY key_code LIMIT 5")

    await conn.close()

    print(f"\nDone! {count} rows in citydb.census_boundaries")
    print("Sample rows:")
    for r in sample:
        print(f"  {r['key_code']}  {r['moji']}")


asyncio.run(main())
