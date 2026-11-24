from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, InvalidRasterError
from app.core.logging import get_logger
from app.db.models import Raster
from app.gis.crs import ensure_utm_crs
from app.gis.raster import compute_ndsm, inspect_raster, reproject_raster

logger = get_logger(__name__)


async def load_raster_metadata(db: AsyncSession, raster_id: int) -> dict:
    raster = await db.get(Raster, raster_id)
    if raster is None:
        raise AppError(f"Raster #{raster_id} not found.")
    return {
        "id": raster.id,
        "file_path": raster.file_path,
        "crs": raster.crs,
        "width": raster.width,
        "height": raster.height,
        "bands": raster.bands,
        "resolution": raster.resolution,
        "bounds_json": raster.bounds_json,
        "nodata": raster.nodata,
    }


async def reproject_raster_to_utm(db: AsyncSession, raster_id: int, output_path: str) -> str:
    raster = await db.get(Raster, raster_id)
    if raster is None:
        raise AppError(f"Raster #{raster_id} not found.")

    src_path = raster.file_path
    with rasterio.open(src_path) as src:
        bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
        crs_str = str(src.crs) if src.crs else "EPSG:4326"

    if "UTM" in crs_str or (src.crs and src.crs.is_projected):
        target_crs = crs_str
    else:
        target_crs = str(ensure_utm_crs(bounds))

    result = reproject_raster(src_path, output_path, target_crs)
    logger.info("Reprojected raster %d to %s -> %s", raster_id, target_crs, result)
    return str(result)


def get_raster_info(file_path: str) -> dict:
    return inspect_raster(file_path)


def create_nsm(dsm_path: str, dtm_path: str, output_path: str) -> str:
    result = compute_ndsm(dsm_path, dtm_path, output_path)
    logger.info("Created nDSM: %s", result)
    return str(result)
