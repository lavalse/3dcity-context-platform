# 3DCityDB v4 Schema Diagram — Taito-ku PLATEAU Data

Two diagrams below. The first shows the big picture (all populated feature types). The second shows building tables in detail.

---

## Diagram 1 — Big Picture

All feature tables share the same pattern: every row in a feature table (`building`, `land_use`, etc.) has a matching row in `cityobject`. The `cityobject` row holds the `gmlid` identifier and bounding box. The feature table holds the domain-specific attributes.

```mermaid
erDiagram

    objectclass {
        int     id          PK
        string  classname
    }

    cityobject {
        bigint  id              PK
        int     objectclass_id  FK
        string  gmlid
        geometry envelope
    }

    surface_geometry {
        bigint  id              PK
        bigint  parent_id       FK
        bigint  root_id         FK
        bigint  cityobject_id   FK
        geometry geometry
        geometry solid_geometry
    }

    cityobject_genericattrib {
        bigint  id              PK
        bigint  cityobject_id   FK
        string  attrname
        string  strval
        int     intval
        float   realval
    }

    building {
        bigint  id                  PK
        bigint  building_root_id    FK
        bigint  building_parent_id  FK
        float   measured_height
        int     storeys_above_ground
        string  usage
        bigint  lod1_solid_id       FK
        bigint  lod2_solid_id       FK
    }

    thematic_surface {
        bigint  id                      PK
        bigint  building_id             FK
        int     objectclass_id          FK
        bigint  lod2_multi_surface_id   FK
    }

    address {
        bigint  id              PK
        string  street
        string  house_number
        string  city
        geometry multi_point
    }

    address_to_building {
        bigint  building_id     FK
        bigint  address_id      FK
    }

    land_use {
        bigint  id                      PK
        string  class
        string  function
        string  usage
        bigint  lod1_multi_surface_id   FK
    }

    transportation_complex {
        bigint  id                      PK
        string  type
        string  function
        bigint  lod2_multi_surface_id   FK
    }

    traffic_area {
        bigint  id                          PK
        string  function
        bigint  transportation_complex_id   FK
        bigint  lod2_multi_surface_id       FK
    }

    waterbody {
        bigint  id                      PK
        string  class
        string  function
        bigint  lod0_multi_surface_id   FK
        bigint  lod1_multi_surface_id   FK
    }

    objectclass              ||--o{ cityobject                   : "classifies"
    cityobject               ||--|{ surface_geometry             : "owns geometry"
    cityobject               ||--o{ cityobject_genericattrib     : "has attributes"

    cityobject               ||--|| building                     : "is-a"
    cityobject               ||--|| land_use                     : "is-a"
    cityobject               ||--|| transportation_complex       : "is-a"
    cityobject               ||--|| traffic_area                 : "is-a"
    cityobject               ||--|| waterbody                    : "is-a"
    cityobject               ||--|| thematic_surface             : "is-a"

    building                 ||--o{ building                     : "root-parent"
    building                 ||--o{ thematic_surface             : "has surfaces"
    building                 }o--o{ address_to_building          : "link"
    address                  }o--o{ address_to_building          : "link"

    transportation_complex   ||--o{ traffic_area                 : "contains"

    surface_geometry         ||--o{ surface_geometry             : "parent-root tree"
```

---

## Diagram 2 — Building Tables in Detail

How to navigate from a top-level building to its geometry, surfaces, and attributes.

```mermaid
erDiagram

    cityobject {
        bigint      id              PK
        string      gmlid
        int         objectclass_id  FK
        geometry    envelope
    }

    building {
        bigint  id                      PK
        bigint  building_root_id        FK
        bigint  building_parent_id      FK
        float   measured_height
        int     storeys_above_ground
        int     storeys_below_ground
        string  usage
        string  class
        bigint  lod1_solid_id           FK
        bigint  lod2_solid_id           FK
        bigint  lod2_multi_surface_id   FK
    }

    thematic_surface {
        bigint  id                      PK
        bigint  building_id             FK
        int     objectclass_id          FK
        bigint  lod2_multi_surface_id   FK
    }

    surface_geometry {
        bigint      id              PK
        bigint      parent_id       FK
        bigint      root_id         FK
        bigint      cityobject_id   FK
        int         is_solid
        geometry    geometry
        geometry    solid_geometry
    }

    cityobject_genericattrib {
        bigint  id              PK
        bigint  cityobject_id   FK
        string  attrname
        int     datatype
        string  strval
        int     intval
        float   realval
    }

    address {
        bigint      id          PK
        string      street
        string      house_number
        geometry    multi_point
    }

    address_to_building {
        bigint  building_id     FK
        bigint  address_id      FK
    }

    cityobject          ||--||  building                    : "id shared (is-a)"
    building            ||--o{  building                    : "root / parent"
    building            ||--o{  thematic_surface            : "wall / roof / ground"
    building            ||--||  surface_geometry            : "lod1_solid_id"
    building            |o--||  surface_geometry            : "lod2_solid_id"
    thematic_surface    |o--||  surface_geometry            : "lod2_multi_surface_id"
    surface_geometry    ||--o{  surface_geometry            : "parent / root tree"
    cityobject          ||--o{  cityobject_genericattrib    : "uro ADE attributes"
    building            }o--o{  address_to_building         : "link"
    address             }o--o{  address_to_building         : "link"
```

---

## How to Navigate Between Tables

| Goal | Join path |
|---|---|
| Building attributes + GML ID | `building` JOIN `cityobject` ON `cityobject.id = building.id` |
| Building LOD1 solid geometry | `building` JOIN `surface_geometry` ON `surface_geometry.id = building.lod1_solid_id` |
| Building roof surfaces | `building` JOIN `thematic_surface` ON `thematic_surface.building_id = building.id` WHERE `objectclass_id = 34` |
| Building wall surfaces | same JOIN, WHERE `objectclass_id = 33` |
| Building ground surfaces | same JOIN, WHERE `objectclass_id = 35` |
| Building address | `building` JOIN `address_to_building` ON `building_id` JOIN `address` ON `address_id` |
| ADE attributes (uro:) | `cityobject` JOIN `cityobject_genericattrib` ON `cityobject_id = cityobject.id` WHERE `attrname = 'uro:...'` |
| Land use zones | `land_use` JOIN `cityobject` ON `cityobject.id = land_use.id` |
| Roads | `transportation_complex` JOIN `traffic_area` ON `traffic_area.transportation_complex_id = transportation_complex.id` |
| Flood zones | `cityobject` WHERE `objectclass_id = 9` (stored as WaterBody) |
| Spatial overlap | `co1.envelope && co2.envelope` for bbox pre-filter, then `ST_Intersects` for exact check |

## Tables NOT Populated in Taito-ku

These tables exist in the schema but have no data in the current import:

`bridge`, `bridge_*`, `tunnel`, `tunnel_*`, `room`, `building_furniture`, `opening`, `relief_*`, `plant_cover`, `solitary_vegetat_object`, `city_furniture`, `appearance`, `surface_data`, `textureparam`
