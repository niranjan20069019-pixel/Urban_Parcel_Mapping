# API Documentation

FastAPI app `app/main.py`. Every route is mounted under the prefix
`API_PREFIX` (`/api/v1` by default). OpenAPI/Swagger UI is served at
`/api/v1/docs` and redoc at `/api/v1/redoc`. All route modules are in
`app/api/routes/`.

Geometry is exchanged as **GeoJSON** objects (Shapely `mapping()`), spatial
storage is **EPSG:4326**. Errors follow `{"detail": ..., "error": ..., "details": ...}`
with handlers in `app/main.py` (400/404/422/500).

## Projects — `app/api/routes/projects.py`

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects` | List projects |
| GET | `/api/v1/projects/{project_id}` | Project detail |
| PUT | `/api/v1/projects/{project_id}` | Update |
| DELETE | `/api/v1/projects/{project_id}` | Delete (204) |
| GET | `/api/v1/projects/{project_id}/summary` | Status rollup: dataset counts, parcel statuses, change summary |

## Upload — `app/api/routes/upload.py` (sub-prefix `/upload`)

All accept `project_id` (query), `file` (multipart), optional `name`.
Files land in `{DATA_DIR}/project_{id}/raw/`; a `datasets` row (and for
rasters a `rasters` row) is created, and the raster is metadata-inspected.

| Method | Path | Accepted |
|--------|------|----------|
| POST | `/api/v1/upload/raster | tif, tiff, img, jpg, jpeg, png |
| POST | `/api/v1/upload/vector` | shp, zip, geojson, json, gml, kml, dxf |
| POST | `/api/v1/upload/gnss` | csv, txt, gpx |
| POST | `/api/v1/upload/{project_id}/all` | any of the above (multipart, one file) |

Returns dataset JSON (201). Bad extensions → 400; unreadable raster → 422.

## Imagery / datasets — `app/api/routes/imagery.py`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/projects/{project_id}/datasets` | List dataset rows |
| GET | `/api/v1/datasets/{dataset_id}/info` | `RasterInfo`: crs, size, bands, resolution, bounds, nodata, dtype |
| POST | `/api/v1/datasets/{dataset_id}/reproject` | Params `target_crs`, `resampling` (default `nearest`); writes `{stem}_{CRS}{ext}` alongside source, registers new dataset+raster |
| GET | `/api/v1/datasets/{dataset_id}/tiles` | `{tiled: bool, tiles: [names]}` from `../tiles/` |

## Inference — `app/api/routes/inference.py`

`MODEL_CHECKPOINTS` maps the four primary tasks to checkpoint paths:
`segformer_building`, `segformer_road`, `segformer_landuse`,
`segformer_boundary`. `SUPPORTED_MODELS` also accepts short aliases
`building|road|landuse|boundary`. Per-project in-memory run status is kept
in `_run_status`.

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/projects/{project_id}/inference/{model_name}` | Run one model. Unknown model → 404. Missing checkpoint → `ModelNotFoundError` (404). Returns model result dict (with `is_mock`/`mock_label` in demo mode). |
| POST | `/api/v1/projects/{project_id}/inference/run` | Run all four configured models; skips (status `SKIPPED`) models with no checkpoint instead of failing. |
| GET | `/api/v1/projects/{project_id}/inference/status` | Running state + last 10 runs + history count |
| GET | `/api/v1/projects/{project_id}/predictions` | Stored `predictions` rows for the project |

Output masks are written to `{DATA_DIR}/project_{id}/predictions/{model}.npy`
plus a `masks_meta.json`. In `DEMO_MODE=1` the model result is a labeled
mock (see `app/core/mock.py`, label `"DEVELOPMENT MOCK — NOT AI PREDICTION"`).

## Features — `app/api/routes/features.py`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/projects/{project_id}/buildings` | id, area, perimeter, confidence, height, `geom_json` |
| GET | `/api/v1/projects/{project_id}/roads` | + road_class, width, length, `centerline_json` |
| GET | `/api/v1/projects/{project_id}/landuse` | + landuse_class, area |
| GET | `/api/v1/projects/{project_id}/boundaries` | + boundary_type (boundary evidence, NOT legal parcels) |
| GET | `/api/v1/projects/{project_id}/features/{feature_type}/geojson` | `feature_type` = `buildings|roads|landuse|boundaries` → GeoJSON FeatureCollection |

## Parcels — `app/api/routes/parcels.py`

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/projects/{project_id}/parcels/infer` | Polygonize latest `predictions/segformer_boundary.npy` → `AI_GENERATED` parcels. No mask → 404. |
| GET | `/api/v1/projects/{project_id}/parcels` | List all parcels |
| GET | `/api/v1/parcels/{parcel_id}` | Parcel detail |
| PUT | `/api/v1/parcels/{parcel_id}/edit` | Body `ParcelEditRequest {geom_json, editor, notes?}`; records `SurveyorEdit` (old/new geom), sets status `SURVEYOR_EDITED` |
| POST | `/api/v1/parcels/{parcel_id}/accept` | `validator` param → `FINAL_VALIDATED` + Validation row |
| POST | `/api/v1/parcels/{parcel_id}/reject` | `reason`, `validator` → back to `AI_GENERATED` + Validation row |
| GET | `/api/v1/parcels/{parcel_id}/versions` | Surveyor edit history with old/new GeoJSON |
| GET | `/api/v1/parcels/{parcel_id}/confidence` | Overall + breakdown (ai_agreement, canopy, gnss_agreement, topology_validity, area_plausibility, boundary_evidence) |
| GET | `/api/v1/parcels/{parcel_id}/recommendations` | Priority-ordered recommendations + evidence |

`ParcelResponse`: `{id, project_id, version, status, area, perimeter,
confidence, change_type?, geom_json, metadata?, created_at, updated_at}`.

## Comparison — `app/api/routes/comparison.py`

Compares two parcel status cohorts:
`POST /api/v1/projects/{project_id}/compare`
Params: `old_status` (default `OLD`), `new_status` (default `AI_GENERATED`).
Pairing is greedy max-IoU over normalized geometries; unmatched old parcels →
`REMOVED`, unmatched new → `NEW`.

`_classify_change(iou, area_diff, centroid_dist)` thresholds:

| Condition | ChangeType |
|-----------|-----------|
| `iou >= 0.9` | `UNCHANGED` |
| `area_diff < -0.7 and iou < 0.3` | `SUBDIVISION` |
| `area_diff > 1.0 and iou < 0.3` | `MERGER` |
| `centroid_dist > 10.0 and iou < 0.3` | `NEW` |
| `0.3 <= iou < 0.9` | `BOUNDARY_SHIFT` |
| otherwise | `UNCERTAIN` |

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/projects/{project_id}/changes` | `parcel_changes` rows |
| GET | `/api/v1/projects/{project_id}/changes/summary` | Per-status counts, `change_type` histogram, high-confidence (≥ 0.8) flag |

## Validation — `app/api/routes/validation.py`

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/projects/{project_id}/validate/topology` | Runs `validate_parcel_topology` (overlap, self-intersection, duplicate, sliver); replaces prior `topology_issues` for the project |
| POST | `/api/v1/projects/{project_id}/validate/repair` | Applies `repair_geometry` to each parcel; re-reports topology after |
| GET | `/api/v1/projects/{project_id}/topology-issues` | List issues (with `parcel_id`, severity, geometry) |

## GNSS — `app/api/routes/gnss.py`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/projects/{project_id}/gnss/points` | `limit` (≤ 10000); includes point_id, lat/lon, height, accuracy |
| POST | `/api/v1/projects/{project_id}/gnss/validate` | `tolerance_m` (default 5.0). Each point → `inside_parcel`/`outside` + nearest parcel + `accuracy_flag`; returns totals |
| POST | `/api/v1/projects/{project_id}/gnss/match` | Greedy match points→parcels; **flags matched parcels `GNSS_VALIDATED`** and writes a `Validation` row |

## Surveyor — `app/api/routes/surveyor.py`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/projects/{project_id}/surveyor/queue` | `status_filter` optional; default `AI_GENERATED`/`SURVEYOR_EDITED`, ordered lowest confidence first |
| POST | `/api/v1/projects/{project_id}/surveyor/{parcel_id}/edit` | Same as `PUT /parcels/{id}/edit` (surveyor-branded) |
| POST | `/api/v1/projects/{project_id}/surveyor/{parcel_id}/accept` | `editor` param → `FINAL_VALIDATED` |
| POST | `/api/v1/projects/{project_id}/surveyor/{parcel_id}/reject` | `reason`, `editor` → back to `AI_GENERATED` |
| POST | `/api/v1/projects/{project_id}/surveyor/{parcel_id}/field-verify` | Marks `field_verification=required` in metadata |
| GET | `/api/v1/projects/{project_id}/surveyor/stats` | Counts by parcel status, validation status, edits per surveyor |

## Export — `app/api/routes/export.py`

Builds GeoDataFrames from the DB and streams files.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/projects/{project_id}/export/parcels` | `format` = `geojson`\|`csv`, attachment download |
| GET | `/api/v1/projects/{project_id}/export/features/{feature_type}` | `buildings|roads|landuse|boundaries` → GeoJSON/CSV |
| GET | `/api/v1/projects/{project_id}/export/csv` | Combined CSV (all feature types) |
| GET | `/api/v1/projects/{project_id}/export/full` | ZIP bundle (parcels + features + predictors) |

## Health / system

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | `{status, service, version}` |