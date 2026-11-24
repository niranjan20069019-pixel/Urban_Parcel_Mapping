from __future__ import annotations

from pathlib import Path

import rasterio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, DatasetError, InvalidRasterError
from app.core.logging import get_logger
from app.db.models import Dataset, Project, Raster
from app.gis.raster import inspect_raster

logger = get_logger(__name__)

_RASTER_EXTENSIONS = {".tif", ".tiff"}
_VECTOR_EXTENSIONS = {".shp", ".geojson", ".gpkg"}


def _detect_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext in _RASTER_EXTENSIONS:
        return "raster"
    if ext in _VECTOR_EXTENSIONS:
        return "vector"
    if ext == ".csv":
        return "gnss"
    raise DatasetError(f"Cannot auto-detect type for extension '{ext}'.")


async def validate_uploaded_file(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise DatasetError(f"File not found: {path}")

    file_type = _detect_type(path)
    meta: dict = {"path": str(p), "file_type": file_type, "size_bytes": p.stat().st_size}

    if file_type == "raster":
        try:
            meta["raster_info"] = inspect_raster(path)
        except Exception as exc:
            raise InvalidRasterError(f"Cannot read raster: {exc}") from exc

    return meta


async def ingest_raster(
    db: AsyncSession,
    project_id: int,
    file_path: str,
    dataset_type: str = "raster",
) -> Dataset:
    project = await db.get(Project, project_id)
    if project is None:
        raise AppError(f"Project #{project_id} not found.")

    meta = await validate_uploaded_file(file_path)
    ds = Dataset(
        project_id=project_id,
        name=Path(file_path).stem,
        dataset_type=dataset_type,
        file_path=str(file_path),
        metadata_json=meta,
    )
    db.add(ds)
    await db.flush()

    rinfo = meta.get("raster_info", {})
    bounds = rinfo.get("bounds", {})
    raster = Raster(
        dataset_id=ds.id,
        file_path=str(file_path),
        crs=rinfo.get("crs"),
        width=rinfo.get("width", 0),
        height=rinfo.get("height", 0),
        bands=rinfo.get("bands", 1),
        resolution=rinfo.get("resolution", {}).get("x") if isinstance(rinfo.get("resolution"), dict) else None,
        bounds_json=bounds if bounds else None,
        nodata=rinfo.get("nodata"),
    )
    db.add(raster)
    await db.flush()
    await db.refresh(ds)
    logger.info("Ingested raster dataset %d for project %d", ds.id, project_id)
    return ds


async def ingest_vector(
    db: AsyncSession,
    project_id: int,
    file_path: str,
    dataset_type: str = "vector",
) -> Dataset:
    project = await db.get(Project, project_id)
    if project is None:
        raise AppError(f"Project #{project_id} not found.")

    meta = await validate_uploaded_file(file_path)
    ds = Dataset(
        project_id=project_id,
        name=Path(file_path).stem,
        dataset_type=dataset_type,
        file_path=str(file_path),
        metadata_json=meta,
    )
    db.add(ds)
    await db.flush()
    await db.refresh(ds)
    logger.info("Ingested vector dataset %d for project %d", ds.id, project_id)
    return ds


async def ingest_gnss(
    db: AsyncSession,
    project_id: int,
    file_path: str,
    crs: str = "EPSG:4326",
) -> Dataset:
    project = await db.get(Project, project_id)
    if project is None:
        raise AppError(f"Project #{project_id} not found.")

    meta = await validate_uploaded_file(file_path)
    meta["assumed_crs"] = crs
    ds = Dataset(
        project_id=project_id,
        name=Path(file_path).stem,
        dataset_type="gnss",
        file_path=str(file_path),
        metadata_json=meta,
    )
    db.add(ds)
    await db.flush()
    await db.refresh(ds)
    logger.info("Ingested GNSS dataset %d for project %d", ds.id, project_id)
    return ds
