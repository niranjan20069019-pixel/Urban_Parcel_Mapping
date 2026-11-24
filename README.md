# Urban Parcel Mapping — AI-Based Cadastral Feature Extraction

End-to-end geospatial pipeline: satellite/orthoimagery → AI segmentation →
vector parcels → surveyor/GNSS verification → export. Backend FastAPI +
PostGIS, frontend Vite/React, Torch models.

> **Legal disclaimer.** Everything this system produces from imagery is a
> *proposal*. AI output is never legally authoritative. Only parcels that a
> licensed surveyor reviews and accepts (`FINAL_VALIDATED`) may be used for
> cadastral decisions, and field/GNSS verification is mandatory where the law
> requires it. Boundary evidence extracted from imagery is evidence, not a
> record.

## Pipeline

```
raw imagery (uploads)
  → CRS-normalize (EPSG:4326 store / UTM compute)   gis/crs.py
  → tile (512 px, 64 overlap)                        tiling_service
  → segmentation (building | road | landuse | boundary)
                                                    models/ + inference_service
  → vectorize masks → geometries                     vectorization_service
  → parcel polygons (AI_GENERATED)                   parcel_inference_service
  → topology check / repair                          topology_service
  → compare old vs new (subdivision/merger/…)        comparison_service
  → surveyor queue → edit/accept/reject              surveyor_service
  → GNSS match/validate (GNSS_VALIDATED)             gnss_service
  → accept → FINAL_VALIDATED                         parcels API
  → export GeoJSON/CSV/ZIP                           export_service
```

Parcel status state machine: `OLD → AI_GENERATED → SURVEYOR_EDITED →
GNSS_VALIDATED → FINAL_VALIDATED`. Every edit/mutation writes an audit row;
geometry history is fully reconstructable.

## Repository layout

```
backend/   FastAPI app (app/), tests/, pytest.ini, Dockerfile, requirements.txt
frontend/  Vite + React + TS, nginx Docker
docs/      14 docs: ARCHITECTURE, API_DOCUMENTATION, DATABASE_SCHEMA, DEPLOYMENT,
           MODEL_*, GIS_WORKFLOW, PARCEL_INFERENCE, CHANGE_DETECTION,
           GNSS_WORKFLOW, SURVEYOR_WORKFLOW, CODE_EXPLANATION
models/    configs/*.yaml + README; checkpoints go in models/checkpoints/{task}/model.pth
scripts/   run_pipeline.py, setup.py, validate_environment.py
data/      project_{id}/{raw,tiles,predictions,vectors,parcels,gnss,exports}
```

## 1. Prerequisites

- Python 3.10+ (3.12 in Docker), Node 20
- PostgreSQL + PostGIS (docker compose provides it)
- Linux build libs for GDAL/GEOS/PROJ if installing rasterio/geopandas from
  source

## 2. Install

```bash
# backend
cd backend && pip install -r requirements.txt

# frontend
cd frontend && npm install
```

This repo's venv (used in docs below) lives at `.venv/` at the repo root.

## 3. Configure

```bash
cp .env.example .env      # edit DATABASE_URL, DEMO_MODE, etc. (see DEPLOYMENT.md)
python scripts/setup.py   # create data/ + models/checkpoints dirs
```

## 4. Database

```bash
docker compose up -d postgres            # PostGIS 16
make migrate                             # create_all
python scripts/validate_environment.py   # verify DB reachability + stack
```

## 5. Run backend

```bash
make dev-backend     # uvicorn app.main:app --reload --port 8000
```

Swagger: `http://localhost:8000/api/v1/docs`

## 6. Run frontend

```bash
make dev-frontend    # Vite dev server (proxies /api → :8000)
```

## 7. Demo mode (no weights)

`DEMO_MODE=1` in `.env`. Inference returns *labeled mocks*
(`DEVELOPMENT MOCK — NOT AI PREDICTION`), so the whole pipeline runs end to
end without model checkpoints. Outputs are visibly labeled and must never be
treated as real predictions.

## 8. Install model checkpoints

Paste trained weights at:
```
models/checkpoints/building/model.pth
models/checkpoints/road/model.pth
models/checkpoints/landuse/model.pth
models/checkpoints/boundary/model.pth
```
Without weights, single-model inference is 404 and `inference/run` skips the
missing tasks. See `docs/MODEL_TRAINING.md` to train them.

## 9. Run the pipeline (API)

```bash
# create project → upload raster → infer → parcels → validate → export
curl -s -X POST http://localhost:8000/api/v1/projects
curl -s -X POST "http://localhost:8000/api/v1/upload/raster?project_id=1" -F file=@ortho.tif
curl -s -X POST http://localhost:8000/api/v1/projects/1/inference/run
curl -s -X POST http://localhost:8000/api/v1/projects/1/parcels/infer
curl -s -X POST http://localhost:8000/api/v1/projects/1/validate/topology
curl -s -o parcels.geojson http://localhost:8000/api/v1/projects/1/export/parcels
```
Full endpoint reference: `docs/API_DOCUMENTATION.md`.

## 10. Run the pipeline (CLI)

```bash
python scripts/run_pipeline.py --project-id 1
python scripts/run_pipeline.py --project-id 1 --demo
# flags: --skip-inference --skip-parcels --skip-comparison
```

## 11. Surveyor workflow

`GET /surveyor/queue` → lowest-confidence-first review → `edit` / `accept` /
`reject` / `field-verify`. See `docs/SURVEYOR_WORKFLOW.md`.

## 12. GNSS validation

`upload/gnss` → `gnss/validate` (distance to boundary) → `gnss/match` (flags
matched parcels `GNSS_VALIDATED`). See `docs/GNSS_WORKFLOW.md`.

## 13. Change detection / comparison

`POST /projects/{id}/compare?old_status=OLD&new_status=AI_GENERATED` → change
types (subdivision, merger, new, boundary-shift, unchanged, uncertain) stored
as `parcel_changes`. See `docs/CHANGE_DETECTION.md`.

## 14. Confidence

`GET /parcels/{id}/confidence` → overall + breakdown
(ai_agreement, canopy, gnss_agreement, topology_validity, area_plausibility,
boundary_evidence). See `docs/MODEL_DECISION_MATRIX.md`.

## 15. Tests

```bash
cd backend && .venv/../../.venv/bin/python -m pytest -q
```
DB-dependent tests skip if PostGIS creds differ. In this repo the venv is at
repo root: `cd backend && ../.venv/bin/python -m pytest -q`.
Status: **26 passed, 1 skipped** (no DB).

## 16. Docs index

| Doc | Purpose |
|-----|---------|
| `docs/ARCHITECTURE.md` | System diagram + module responsibilities |
| `docs/DATA_FLOW.md` | End-to-end data movement |
| `docs/API_DOCUMENTATION.md` | All endpoints |
| `docs/DATABASE_SCHEMA.md` | Tables, enums, spatial indexes |
| `docs/DEPLOYMENT.md` | Env vars, Docker, production notes |
| `docs/MODEL_INTEGRATION.md` | Registry, adapters, adding a model |
| `docs/MODEL_TRAINING.md` | Dataset prep + training recipe |
| `docs/MODEL_DECISION_MATRIX.md` | Which model for which output |
| `docs/GIS_WORKFLOW.md` | CRS, tiling, topology, export |
| `docs/PARCEL_INFERENCE.md` | Mask → parcel polygonization |
| `docs/CHANGE_DETECTION.md` | Comparison + classification |
| `docs/GNSS_WORKFLOW.md` | Field validation flow |
| `docs/SURVEYOR_WORKFLOW.md` | Human-in-the-loop review gate |
| `docs/CODE_EXPLANATION.md` | Per-module WHAT/WHY/INPUT/OUTPUT |

## 17. Docker

```bash
make docker-up     # postgres + backend + frontend (nginx)
make docker-down
```

## 18. Known limitations

- No checkpoints shipped — pipeline is 404/skip until weights are installed
  (or `DEMO_MODE=1`).
- AI-generated parcels are proposals only; legal adoption requires surveyor
  acceptance and, where required, field/GNSS verification.
- PostGIS availability is optional for unit tests but required for the API.
- Future adapters (change detection, confidence, GAT) run on labeled
  fallbacks until trained (see `docs/MODEL_INTEGRATION.md`).

## 19. Next step

Train Building SegFormer-B2 (`docs/MODEL_TRAINING.md`), drop weights into
`models/checkpoints/building/model.pth`, then run inference for real:
`POST /api/v1/projects/{id}/inference/building`.