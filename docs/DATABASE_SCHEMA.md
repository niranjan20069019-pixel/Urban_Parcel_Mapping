# Database Schema

PostgreSQL + PostGIS. Managed through SQLAlchemy 2.0 (async) in
`backend/app/db/models.py`; `init_db()` runs `create_all` on startup.

## Tables

### projects
| Column | Notes |
|--------|-------|
| id | PK |
| name | unique-ish display name |
| description | text |
| status | e.g. `ACTIVE` |
| created_at / updated_at | timezone-aware |

Relationships: datasets, parcels, gnss_points, topology_issues, parcel_changes.

### datasets
| Column | Notes |
|--------|-------|
| id | PK |
| project_id | FK → projects (CASCADE) |
| name | display name |
| dataset_type | `raster` \| `vector` \| `gnss` |
| file_path | path under `data/` |
| metadata_json | inspect_raster() output or origin info |
| created_at | |

### rasters
| Column | Notes |
|--------|-------|
| id | PK |
| dataset_id | FK → datasets (CASCADE) |
| file_path | |
| crs | e.g. `EPSG:32645` |
| width / height / bands | int |
| resolution | float (x resolution) |
| bounds_json | `{left,bottom,right,top}` |
| nodata | float or null |

### predictions
| Column | Notes |
|--------|-------|
| id | PK |
| raster_id | FK → rasters (CASCADE) |
| model_name | e.g. `segformer_boundary` |
| model_version | reproducibility |
| checkpoint_path | reproducibility |
| class_mapping_json | class id → name |
| file_path | `.npy` mask location |

Relationships: buildings, roads, landuse_features, boundary_evidences.

### buildings
| Column | Notes |
|--------|-------|
| prediction_id | FK → predictions |
| project_id | FK → projects |
| geom | MULTIPOLYGON (srid 4326) |
| area / perimeter | computed |
| centroid | POINT |
| confidence | mean mask confidence |
| height | from nDSM if available |
| metadata_json | |

### roads
`id, prediction_id, project_id, geom (MULTIPOLYGON), centerline
(MULTILINESTRING), road_class, width, length, confidence`

### landuse_features
`id, prediction_id, project_id, geom (MULTIPOLYGON), landuse_class, area,
confidence`

### boundary_evidences
`id, prediction_id, project_id, geom (MULTILINESTRING), boundary_type,
confidence`

Boundary evidence is stored **separately** from parcels: visible walls/fences
are evidence, never a legal record.

### parcels
| Column | Notes |
|--------|-------|
| id | PK |
| project_id | FK → projects |
| geom | MULTIPOLYGON (srid 4326) |
| version | increments on each edit |
| status | `OLD` \| `AI_GENERATED` \| `SURVEYOR_EDITED` \| `GNSS_VALIDATED` \| `FINAL_VALIDATED` |
| area / perimeter | computed |
| centroid | POINT |
| confidence | weighted score |
| change_type | set by comparison stage |
| parent_parcel_id | FK → parcels (self), subdivision/merger lineage |
| metadata_json | reasoning, field verification flags |

Parcel **version history**: the live geometry is stored in `parcels.geom`;
every edit additionally writes a `surveyor_edits` row with old/new geometry,
so the full chain `OLD → AI → edited → validated` is reconstructable.

### surveyor_edits
`id, parcel_id, editor, old_geom (MULTIPOLYGON), new_geom (MULTIPOLYGON),
notes, created_at`

### validations
`id, parcel_id, validator, validation_type, status, notes, created_at`
Audit trail for every accept/reject/field-verify/GNSS transition.

### gnss_points
`id, project_id, point_id, geom (POINT 4326), latitude, longitude, height,
accuracy, timestamp, crs, source`

### topology_issues
`id, project_id, parcel_id (nullable), issue_type (overlap |
self_intersection | duplicate | gap | sliver), description, geom, severity,
resolved, created_at`

### parcel_changes
`id, project_id, old_parcel_id, new_parcel_id, change_type, confidence,
evidence_json, created_at`

### recommendations
`id, parcel_id, action, priority, reason, evidence_json, created_at,
acknowledged_at`

## Indexes / spatial indexes

- Geometry columns use PostGIS `Geometry` types → spatial indexes on
  `geom` in parcels, buildings, roads, landuse_features, boundary_evidences,
  surveyor_edits, gnss_points, topology_issues.
- FKs on `project_id` / `parcel_id` / `raster_id` are indexed by FK
  constraints; heavy list queries additionally rely on `project_id`+`status`
  (surveyor queue) and `parcel_id` (validations, recommendations).

GeoAlchemy2 writes geometries as WKB over the asyncpg driver; SQLAlchemy
`Mapped[Any]` + `Geometry(srid=4326)` handles it. Reading geometry uses
`geoalchemy2.shape.to_shape`, writing uses `WKTElement(wkt, srid=4326)`.