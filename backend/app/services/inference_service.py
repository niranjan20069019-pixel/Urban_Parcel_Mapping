from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, ModelInferenceError, ModelNotFoundError
from app.core.logging import get_logger
from app.db.models import Prediction, Project, Raster
from app.gis.raster import inspect_raster
from app.models.segmentation_base import registry
from app.services.tiling_service import stitch_predictions, tile_raster

logger = get_logger(__name__)

DEFAULT_MODELS = ["building", "road", "landuse", "boundary"]


async def _get_raster_for_project(db: AsyncSession, project_id: int) -> Raster:
    result = await db.execute(
        select(Raster)
        .join(Raster.dataset)
        .where(Raster.dataset.has(project_id=project_id))
        .order_by(Raster.id.desc())
        .limit(1)
    )
    raster = result.scalars().first()
    if raster is None:
        raise AppError(f"No raster found for project #{project_id}.")
    return raster


async def run_single_model(
    project_id: int,
    model_name: str,
    tiles_dir: str,
    output_dir: str,
) -> dict | None:
    if _demo_enabled():
        return await _run_demo_model(model_name, tiles_dir, output_dir)
    try:
        adapter = registry.get(model_name)
    except KeyError:
        logger.warning("Model '%s' not registered, skipping.", model_name)
        return None

    if not adapter.loaded:
        try:
            adapter.load_model()
        except Exception as exc:
            logger.warning("Failed to load model '%s': %s", model_name, exc)
            return None

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    mask_dir = out / f"{model_name}_masks"
    mask_dir.mkdir(exist_ok=True)

    from app.services.tiling_service import tile_raster

    tile_meta_path = Path(tiles_dir) / "tiles_meta.json"
    if tile_meta_path.exists():
        import json
        with open(tile_meta_path) as f:
            meta = json.load(f)
        tile_paths = [t["path"] for t in meta["tiles"]]
    else:
        tile_paths = sorted(str(p) for p in Path(tiles_dir).glob("tile_*.*"))

    results = []
    for tp in tile_paths:
        with rasterio.open(tp) as src:
            img = src.read()  # (C, H, W)
            if img.shape[0] == 1:
                img = np.repeat(img, 3, axis=0)
            elif img.shape[0] == 4:
                img = img[:3]

            img_hwc = np.transpose(img, (1, 2, 0))  # (H, W, C)

        try:
            pred = adapter.predict(img_hwc)
            mask = pred.get("mask", np.zeros((img_hwc.shape[0], img_hwc.shape[1]), dtype=np.int32))
            tile_name = Path(tp).stem
            mask_path = mask_dir / f"{tile_name}_mask.npy"
            np.save(str(mask_path), mask)
            results.append(str(mask_path))
        except Exception as exc:
            logger.warning("Inference failed on %s with model '%s': %s", tp, model_name, exc)

    logger.info("Model '%s' produced %d masks in %s", model_name, len(results), mask_dir)
    return {
        "model_name": model_name,
        "masks_dir": str(mask_dir),
        "mask_count": len(results),
    }


async def run_inference(
    project_id: int,
    raster_path: str,
    models_to_run: list[str] | None = None,
) -> list[dict]:
    models = models_to_run or DEFAULT_MODELS

    tiles_dir = str(settings.DATA_DIR / f"project_{project_id}" / "tiles")
    output_dir = str(settings.DATA_DIR / f"project_{project_id}" / "predictions")

    tile_infos = tile_raster(
        raster_path,
        tiles_dir,
        tile_size=settings.TILE_SIZE,
        overlap=settings.TILE_OVERLAP,
    )

    with rasterio.open(raster_path) as src:
        orig_crs = str(src.crs) if src.crs else None
        orig_transform = src.transform

    results = []
    for model_name in models:
        result = await run_single_model(project_id, model_name, tiles_dir, output_dir)
        if result is not None:
            results.append(result)

    return results


async def orchestrate_full_pipeline(project_id: int) -> dict:
    from app.db.database import SessionLocal

    async with SessionLocal() as db:
        raster = await _get_raster_for_project(db, project_id)
        raster_path = raster.file_path

        info = inspect_raster(raster_path)
        tiles_dir = str(settings.DATA_DIR / f"project_{project_id}" / "tiles")
        output_dir = str(settings.DATA_DIR / f"project_{project_id}" / "predictions")

        tile_infos = tile_raster(raster_path, tiles_dir, tile_size=settings.TILE_SIZE, overlap=settings.TILE_OVERLAP)

        models_run = []
        for model_name in DEFAULT_MODELS:
            result = await run_single_model(project_id, model_name, tiles_dir, output_dir)
            if result is not None:
                pred = Prediction(
                    raster_id=raster.id,
                    model_name=model_name,
                    file_path=result["masks_dir"],
                )
                db.add(pred)
                await db.flush()
                models_run.append({"model": model_name, "prediction_id": pred.id})

        await db.commit()

    return {
        "project_id": project_id,
        "raster_path": raster_path,
        "tile_count": len(tile_infos),
        "models_run": models_run,
        "tiles_dir": tiles_dir,
        "output_dir": output_dir,
    }
