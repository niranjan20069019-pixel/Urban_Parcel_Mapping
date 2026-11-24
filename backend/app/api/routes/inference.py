from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import InvalidRasterError, ModelNotFoundError
from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import Dataset, Prediction, Project, Raster
from app.models.segmentation_base import ModelConfig, registry

logger = get_logger(__name__)

router = APIRouter(tags=["inference"])

# ponytail: in-memory run status; lost on restart, swap for a DB table when monitoring matters.
_run_status: dict[int, list[dict]] = {}

MODEL_CHECKPOINTS = {
    "segformer_building": settings.BUILDING_MODEL_CHECKPOINT,
    "segformer_road": settings.ROAD_MODEL_CHECKPOINT,
    "segformer_landuse": settings.LANDUSE_MODEL_CHECKPOINT,
    "segformer_boundary": settings.BOUNDARY_MODEL_CHECKPOINT,
}

SUPPORTED_MODELS = {
    "building": "segformer_building",
    "segformer_building": "segformer_building",
    "road": "segformer_road",
    "segformer_road": "segformer_road",
    "landuse": "segformer_landuse",
    "segformer_landuse": "segformer_landuse",
    "boundary": "segformer_boundary",
    "segformer_boundary": "segformer_boundary",
}


def _read_rgb(path: str) -> np.ndarray:
    with rasterio.open(path) as src:
        if src.count >= 3:
            arr = src.read([1, 2, 3]).astype(np.float32)
        else:
            band = src.read(1).astype(np.float32)
            arr = np.stack([band, band, band], axis=0)
        nodata = src.nodata
        if nodata is not None:
            arr[arr == nodata] = np.nan
        valid = arr[~np.isnan(arr)]
        if valid.size == 0:
            raise InvalidRasterError(f"Raster {path} has no valid pixels")
        vmin, vmax = float(np.nanmin(valid)), float(np.nanmax(valid))
        rng = vmax - vmin
        arr = (arr - vmin) / rng * 255.0 if rng > 0 else np.zeros_like(arr)
        arr = np.nan_to_num(arr, nan=0.0).astype(np.uint8)
        return arr.transpose(1, 2, 0)


def _set_status(project_id: int, name: str, state: str, message: str = "") -> None:
    _run_status.setdefault(project_id, []).append(
        {
            "model": name,
            "state": state,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project #{project_id} not found")
    return proj


def _get_adapter(model_key: str):
    """Return a loaded adapter instance from the global registry."""
    if model_key not in registry._models:
        adapter_cls = registry.default_model_classes().get(model_key)
        if adapter_cls is None:
            raise ModelNotFoundError(f"Model '{model_key}' is not registered")
        registry.register(
            model_key,
            adapter_cls,
            ModelConfig(architecture=model_key, checkpoint=MODEL_CHECKPOINTS.get(model_key)),
        )
    adapter = registry.get(model_key)
    if not getattr(adapter, "loaded", False):
        try:
            adapter.load_model()
        except FileNotFoundError as exc:
            raise ModelNotFoundError(str(exc))
    return adapter


async def _run_one(
    project_id: int,
    model_key: str,
    db: AsyncSession,
    raise_on_missing: bool,
) -> dict | None:
    try:
        adapter = _get_adapter(model_key)
    except (ModelNotFoundError, KeyError) as exc:
        if raise_on_missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model not available: {exc}")
        logger.info("Model %s unavailable, skipping: %s", model_key, exc)
        return None

    try:
        datasets = (
            await db.execute(
                select(Dataset)
                .where(Dataset.project_id == project_id, Dataset.dataset_type == "raster")
                .order_by(Dataset.id)
            )
        ).scalars().all()
        if not datasets:
            raise InvalidRasterError(f"No raster dataset found for project #{project_id}")
        raster = (
            await db.execute(select(Raster).where(Raster.dataset_id == datasets[0].id))
        ).scalars().first()

        image = _read_rgb(raster.file_path)
        pred = adapter.predict(image)

        out_dir = Path(settings.DATA_DIR) / f"project_{project_id}" / "predictions"
        out_dir.mkdir(parents=True, exist_ok=True)
        mask = pred.get("mask", pred.get("detections"))
        np.save(out_dir / f"{model_key}.npy", mask)

        pred_row = Prediction(
            raster_id=raster.id,
            model_name=model_key,
            model_version=None,
            checkpoint_path=str(adapter.checkpoint_path) if getattr(adapter, "checkpoint_path", None) else None,
            class_mapping_json=getattr(adapter, "class_mapping", {}) or {},
            file_path=str(out_dir / f"{model_key}.npy"),
        )
        db.add(pred_row)
        await db.flush()

        return {
            "status": "completed",
            "model": model_key,
            "output": str(out_dir / f"{model_key}.npy"),
            "class_mapping": adapter.class_mapping,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Inference failed for model %s on project %d", model_key, project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference for '{model_key}' failed: {exc}",
        )


@router.post("/projects/{project_id}/inference/run")
async def run_inference(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_project_or_404(project_id, db)
    result: dict = {"project_id": project_id, "models": {}}
    for model_key in sorted(set(MODEL_CHECKPOINTS)):
        _set_status(project_id, model_key, "RUNNING")
        outcome = await _run_one(project_id, model_key, db, raise_on_missing=False)
        _set_status(
            project_id, model_key,
            "COMPLETED" if outcome else "SKIPPED",
            "" if outcome else "checkpoint or model unavailable",
        )
        result["models"][model_key] = outcome or {"status": "skipped"}
    return result


@router.post("/projects/{project_id}/inference/{model_name}")
async def run_single_model(
    project_id: int,
    model_name: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_project_or_404(project_id, db)
    model_key = SUPPORTED_MODELS.get(model_name.lower())
    if model_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown model '{model_name}'. Supported: {sorted(SUPPORTED_MODELS)}",
        )
    _set_status(project_id, model_key, "RUNNING")
    result = await _run_one(project_id, model_key, db, raise_on_missing=True)
    _set_status(project_id, model_key, "COMPLETED")
    return result


@router.get("/projects/{project_id}/inference/status")
async def inference_status(project_id: int) -> dict:
    history = _run_status.get(project_id, [])
    running = [h for h in history if h["state"] == "RUNNING"]
    return {
        "project_id": project_id,
        "running": running,
        "last_runs": history[-10:],
        "history_count": len(history),
    }


@router.get("/projects/{project_id}/predictions")
async def list_predictions(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    await _get_project_or_404(project_id, db)
    stmt = (
        select(Prediction)
        .join(Raster, Raster.id == Prediction.raster_id)
        .join(Dataset, Dataset.id == Raster.dataset_id)
        .where(Dataset.project_id == project_id)
        .order_by(Prediction.id.desc())
    )
    preds = (await db.execute(stmt)).scalars().all()
    return {
        "project_id": project_id,
        "total": len(preds),
        "predictions": [
            {
                "id": p.id,
                "model_name": p.model_name,
                "model_version": p.model_version,
                "checkpoint_path": p.checkpoint_path,
                "class_mapping": p.class_mapping_json,
                "file_path": p.file_path,
                "created_at": str(p.created_at),
            }
            for p in preds
        ],
    }