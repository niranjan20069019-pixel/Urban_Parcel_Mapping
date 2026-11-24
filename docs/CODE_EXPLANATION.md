# Code Explanation

Per-module WHAT / WHY / INPUT / OUTPUT. Tree under `backend/app/`.

```
app/
├── main.py                  FastAPI entrypoint, middleware, error mapping
├── api/__init__.py
├── api/routes/              HTTP layer (thin: validate → service call → serialize)
├── core/                    Config, exceptions, logging, security, demo mocks
├── db/                      SQLAlchemy engine/session + all ORM models
├── gis/                     Geometry, raster, topology, CRS primitives
├── models/                  Model classes/adapters (SegFormer, Mask2Former, YOLO, future)
├── schemas/                 Pydantic request/response models
└── services/                Orchestration layer (business logic lives here)
```

## `core/`

- **config.py** — pydantic-settings `Settings`; env vars (`DATABASE_URL`,
  checkpoint paths, `DEMO_MODE`, `TILE_SIZE/OVERLAP`, `GPU_ENABLED`,
  `CORS_ORIGINS`, `API_PREFIX`). WHY: one place for all env-driven knobs.
  INPUT: environment/`.env`. OUTPUT: the `settings` singleton.
- **exceptions.py** — typed errors (`CRSError`, `InvalidRasterError`,
  `ModelInferenceError`, `TopologyError`, …). WHY: routes map each to a
  proper HTTP status; keeps services framework-free.
- **logging.py** — `get_logger()` returning a `logging.Logger` per module.
- **security.py** — secret hashing for API keys (currently inert).
- **mock.py** — `build_mock_mask(image, model_name, seed)` generates a
  *deterministic, labeled* fake mask per model plus `MOCK_LABEL =
  "DEVELOPMENT MOCK — NOT AI PREDICTION"`. WHY: demo/CI without weights;
  the label guarantees mocked output can never be mistaken for a real
  prediction. INPUT: image array, model name, seed. OUTPUT: 2-D uint8 mask.

## `db/`

- **database.py** — async engine/session (`create_async_engine`,
  `async_sessionmaker`), `get_db` dependency, `init_db()` →
  `Base.metadata.create_all`. PostGIS geometries via
  `Geometry(srid=4326)` + `geoalchemy2`.
- **models.py** — all tables: `Project, Dataset, Raster, Prediction,
  Building, Road, LanduseFeature, BoundaryEvidence, Parcel, SurveyorEdit,
  Validation, GnssPoint, TopologyIssue, ParcelChange, Recommendation`
  (see `docs/DATABASE_SCHEMA.md`). `ParcelStatus` enum is the pipeline
  state machine.

## `gis/` — pure geometry, no HTTP/DB coupling

- **crs.py** — `inspect_raster`, `ensure_utm_crs`, `reproject_raster`.
  WHY: model tiling must happen in metres (UTM), while storage stays 4326.
- **raster.py** — raster I/O + slicing (`read_raster_window`, save masks).
- **tiling.py** — sliding-window tile generator with overlap for seam-free
  inference.
- **vector.py** — raster → vector: `raster_to_shapes`, polygonize,
  simplify.
- **geometry.py** — `repair_geometry` (`buffer(0)`/`make_valid`),
  distance helpers, merge/split/centroid utilities.
- **topology.py** — `validate_parcel_topology`: overlap,
  self-intersection, duplicate, sliver detection over a GeoDataFrame.
- **spatial_index.py** — R-tree wrapper (`rtree`) for fast nearest/within
  during matching.
- **distance.py** — ground-distance helpers.

## `models/` — one class per deep model; `segmentation_base.py`

- **segmentation_base.py** — `ModelConfig` + `ModelRegistry` +
  `default_model_classes()`. Registry maps task names
  (`segformer_building`, `segformer_road`, `segformer_landuse`,
  `segformer_boundary`, `mask2former`, `yolo`) to classes and supplies
  checkpoints from settings. THE single gateway for inference; everything
  loadable must be registered here.
- **segformer_{building,road,landuse,boundary}.py** — SMP-based SegFormer
  segmentation classes (same base, different classes/checkpoints).
- **segformer_base.py / mask2former_adapter.py / yolo_adapter.py** — model
  bases/adapters; YOLO raises until `ultralytics` is installed.
- **siamese_change_adapter.py, change_transformer_adapter.py,
  xgboost_confidence_adapter.py, gat_parcel_adapter.py** — *future*
  adapters. Each ships a working fallback (pixel-diff, SSIM-style,
  rule-based confidence, adjacency-based) so the module imports and runs a
  labeled approximation, and transparently uses a real checkpoint if one is
  placed on disk.

## `services/` — the pipeline brain

| Service | Responsibility |
|---------|----------------|
| `ingestion_service` | Accept uploads → Dataset/Raster rows |
| `raster_service` / `preprocessing_service` / `tiling_service` | CRS-normalise, tile, preprocess before inference |
| `inference_service` | Load model from registry, run, save masks; `run_single_model` + `_run_demo_model` (demo branch) and the `run_pipeline`-visible entrypoints |
| `feature_service` / `vectorization_service` | Masks → vector polygons (buildings/roads/landuse/boundaries) + DB rows |
| `parcel_inference_service` | boundary mask → polygonized `AI_GENERATED` parcels |
| `confidence_service` | `ConfidenceFactor` model: weighted `ai_agreement`, `boundary_evidence`, etc. |
| `topology_service` | Run `gis.topology`, store `TopologyIssue`s, repair |
| `comparison_service` / `change_detection_service` | old cohort vs new cohort → `ParcelChange` rows (subdivision/merger/new/boundary-shift/unchanged/uncertain) |
| `gnss_service` | points → parcel match/validate → `GNSS_VALIDATED` |
| `surveyor_service` | queue, edit, accept/reject, field-verify; writes `SurveyorEdit` + `Validation` audit rows |
| `parcel_service` | CRUD + version history + recommendations feed |
| `recommendation_service` | rule-triggered actions per parcel |
| `export_service` | GeoDataFrame → GeoJSON/CSV/ZIP |

## `schemas/` — Pydantic v2
`ParcelResponse/ParcelCreate/ParcelEditRequest`, `BuildingResponse`,
`RoadResponse`, `LanduseResponse`, `BoundaryResponse`,
`GnssPointResponse`, `RasterInfo`, `ProjectResponse`, `ChangeType`,
`Recommendation`, `ValidationResponse`, `TopologyIssueResponse`.

## `api/routes/`
Thin handlers; every route validates target project exists, delegates to a
service, maps exceptions → HTTP (see `docs/API_DOCUMENTATION.md` for the
full surface).

## `main.py`
Builds app, CORS, mounts all routers under `/api/v1`, maps typed exceptions
to 400/404/422/500 JSON, exposes `/health`.

## Key invariants

- Geometry in DB is EPSG:4326; compute happens in UTM (`ensure_utm_crs`).
- `Parcel.status` flows `OLD → AI_GENERATED → SURVEYOR_EDITED →
  GNSS_VALIDATED → FINAL_VALIDATED`; only `FINAL_VALIDATED` is intended for
  export as legally-usable cadastre, and every mutation writes an audit row.
- Raster I/O pinning: results stored as `*.npy` masks under
  `data/project_{id}/predictions/` (no downsampling of source data).
- Never trust a mask as geometry: `vectorization_service` and
  `parcel_inference_service` always pass vector output through
  `repair_geometry` and topology validation.