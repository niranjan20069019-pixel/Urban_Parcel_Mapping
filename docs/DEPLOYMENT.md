# Deployment

## Local development

```bash
# PostGIS via Docker (or point DATABASE_URL at an existing PostGIS server)
docker compose up -d postgres

# Backend
make install            # backend pip + frontend npm
python scripts/validate_environment.py   # checks CUDA, DB, Node, data dirs
cp .env.example .env
make migrate            # create_all on the target DB
make dev-backend        # uvicorn on :8000

# Frontend (Vite dev server, proxies /api to :8000)
make dev-frontend
```

API runs on `http://localhost:8000/api/v1`; Swagger at `/api/v1/docs`.
The frontend expects the API at `localhost:8000` (see `frontend/vite.config.ts` proxy).

## Configuration

All settings live in `app/core/config.py`, overridable via environment /
`backend/.env` (pydantic-settings). Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/urban_cadastral` | Async SQLAlchemy URL, PostGIS required |
| `MODEL_CHECKPOINT_DIR` | `models/checkpoints` | Root for model weights |
| `BUILDING/ROAD/LANDUSE/BOUNDARY_MODEL_CHECKPOINT` | `models/checkpoints/{task}/model.pth` | Per-task weights |
| `GPU_ENABLED` | `false` | `cuda` vs `cpu` device selection |
| `DEMO_MODE` | `false` | `1`/`true` → labeled mock predictions (see `app/core/mock.py`) so the full pipeline runs without weights |
| `TILE_SIZE` / `TILE_OVERLAP` | 512 / 64 | Inference tiling |
| `CORS_ORIGINS` | localhost:3000, 5173 | Frontend origins |
| `API_PREFIX` | `/api/v1` | Route prefix |
| `LOG_LEVEL` | INFO | |

Runtime dirs (`data/`, `models/checkpoints/`, logs) are created at startup by
`settings.ensure_dirs()`.

## Model weights

Checkpoints are **not** distributed with the repo; the model classes are
implemented but untrained services must install weights (see
`docs/MODEL_TRAINING.md`). Without weights, single-model inference returns
404 and `POST .../inference/run` skips those models. In demo mode everything
runs on labeled mocks.

Place weights at:
```
models/checkpoints/building/model.pth
models/checkpoints/road/model.pth
models/checkpoints/landuse/model.pth
models/checkpoints/boundary/model.pth
```

## Docker Compose (full stack)

```bash
make docker-up       # compose up -d --build
make docker-down
```

- `postgres` — `postgis/postgis:16-3.4`, DB `urban_cadastral`,
  user/pass `postgres`/`postgres`, health-checked (backend waits on it).
- `backend` — Dockerfile in `backend/`, mounts `./models` and `./data` so
  weights/uploads persist on the host. Requires `libgdal`, `libgeos`,
  `libproj` (installed in image).
- `frontend` — `node:20-alpine` build → `nginx:alpine`, serves the Vite
  `dist/` on :80, proxied to `:3000`.

## Tests

```bash
cd backend
../.venv/bin/python -m pytest -q     # repo-venv path (see README)
```

Tests that need PostGIS (`@db_available`) skip cleanly when the DB
`/api` creds differ. Test config: `backend/pytest.ini`
(`asyncio_mode = auto`); DB-detection marker in `tests/conftest.py`.

## Production notes

- Set `SECRET_KEY` to a real secret; it is currently a placeholder.
- Terminate TLS in front of `:8000`; the API has no auth — add middleware
  when exposing beyond a trusted network.
- `DEMO_MODE` must be `false`; mock masks are labeled and stored, never
  exported as real predictions.
- Parcel output is **surveyor-verified**, never machine-final —
  `AI_GENERATED`/`SURVEYOR_EDITED` statuses exist so a human review gate is
  always present before export (see docs/ARCHITECTURE.md).

## Troubleshooting

- `asyncpg fails to connect` → start PostGIS (`docker compose up -d
  postgres`), check `DATABASE_URL`, confirm `postgis` extension via
  `validate_environment.py`.
- Inference 404 `ModelNotFoundError` → checkpoint missing; set `DEMO_MODE=1`
  to smoke-test the pipeline without weights.
- `rasterio`/GDAL install failures → ensure `libgdal-dev` etc. (as in the
  Dockerfile) before `pip install`.
- GDAL/RTree C-compat issues inside Compose: backend builds from
  `python:3.12-slim` with system GDAL as above.