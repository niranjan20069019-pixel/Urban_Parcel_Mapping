from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import Dataset, Raster
from app.gis.raster import inspect_raster, reproject_raster
from app.schemas.imagery import DatasetResponse, RasterInfo

logger = get_logger(__name__)

router = APIRouter(tags=["imagery"])

RASTER_EXTS = {".tif", ".tiff"}


async def _get_dataset_or_404(dataset_id: int, db: AsyncSession) -> Dataset:
    ds = await db.get(Dataset, dataset_id)
    if ds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset #{dataset_id} not found")
    return ds


async def _get_raster_or_404(dataset_id: int, db: AsyncSession) -> Raster:
    result = await db.execute(select(Raster).where(Raster.dataset_id == dataset_id))
    raster = result.scalars().first()
    if raster is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Raster for dataset #{dataset_id} not found")
    return raster


def _to_response(ds: Dataset) -> DatasetResponse:
    return DatasetResponse(
        id=ds.id,
        project_id=ds.project_id,
        name=ds.name,
        dataset_type=ds.dataset_type,
        file_path=ds.file_path,
        metadata_json=ds.metadata_json,
        created_at=ds.created_at,
    )


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetResponse])
async def list_datasets(project_id: int, db: AsyncSession = Depends(get_db)) -> list[DatasetResponse]:
    result = await db.execute(select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.id))
    return [_to_response(ds) for ds in result.scalars().all()]


@router.get("/datasets/{dataset_id}/info", response_model=RasterInfo)
async def raster_info(dataset_id: int, db: AsyncSession = Depends(get_db)) -> RasterInfo:
    raster = await _get_raster_or_404(dataset_id, db)
    try:
        meta = inspect_raster(raster.file_path)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Cannot inspect raster: {exc}")

    bounds = meta["bounds"]
    res = meta["resolution"]
    return RasterInfo(
        crs=meta["crs"] or "unknown",
        width=meta["width"],
        height=meta["height"],
        bands=meta["bands"],
        resolution=(res["x"], res["y"]),
        bounds=(bounds["left"], bounds["bottom"], bounds["right"], bounds["top"]),
        nodata=meta.get("nodata"),
        dtype=meta["dtype"][0] if meta["dtype"] else "unknown",
    )


@router.post("/datasets/{dataset_id}/reproject")
async def reproject_dataset(
    dataset_id: int,
    target_crs: str,
    resampling: str = "nearest",
    db: AsyncSession = Depends(get_db),
) -> dict:
    ds = await _get_dataset_or_404(dataset_id, db)
    src_path = Path(ds.file_path)
    out_path = src_path.parent / f"{src_path.stem}_{target_crs.replace(':', '')}{src_path.suffix}"

    try:
        reproject_raster(src_path, out_path, target_crs, resampling)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Reprojection failed: {exc}")

    meta = inspect_raster(out_path)
    new_ds = Dataset(
        project_id=ds.project_id,
        name=f"{ds.name}_{target_crs}",
        dataset_type="raster",
        file_path=str(out_path),
        metadata_json={"reprojected_from": ds.file_path, **meta},
    )
    db.add(new_ds)
    await db.flush()
    raster = Raster(
        dataset_id=new_ds.id,
        file_path=str(out_path),
        crs=meta.get("crs"),
        width=meta["width"],
        height=meta["height"],
        bands=meta["bands"],
        resolution=meta["resolution"]["x"],
        bounds_json=meta["bounds"],
        nodata=meta.get("nodata"),
    )
    db.add(raster)
    await db.flush()

    logger.info("Reprojected dataset %d to %s", dataset_id, target_crs)
    return _to_response(new_ds).model_dump()


@router.get("/datasets/{dataset_id}/tiles")
async def list_tiles(dataset_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    ds = await _get_dataset_or_404(dataset_id, db)
    tile_dir = Path(ds.file_path).parent / "tiles"
    if not tile_dir.exists():
        return {"dataset_id": dataset_id, "tiled": False, "tiles": []}

    tiles = sorted(tile_dir.glob("*.tif"))
    return {
        "dataset_id": dataset_id,
        "tiled": True,
        "tile_count": len(tiles),
        "tiles": [str(t) for t in tiles],
    }