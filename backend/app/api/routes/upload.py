from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import Dataset, Project, Raster
from app.gis.raster import inspect_raster

logger = get_logger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

RASTER_EXTS = {".tif", ".tiff"}
VECTOR_EXTS = {".geojson", ".gpkg", ".shp"}
GNSS_EXTS = {".csv", ".geojson"}


def _validate_ext(filename: str, allowed: set[str], label: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label} file extension '{ext}'. Allowed: {sorted(allowed)}",
        )


def _save_upload(upload: UploadFile, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest


def _project_dir(project_id: int) -> Path:
    return settings.DATA_DIR / f"project_{project_id}" / "raw"


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project #{project_id} not found")
    return proj


def _dataset_response(ds: Dataset) -> dict:
    return {
        "id": ds.id,
        "project_id": ds.project_id,
        "name": ds.name,
        "dataset_type": ds.dataset_type,
        "file_path": ds.file_path,
        "metadata_json": ds.metadata_json,
        "created_at": str(ds.created_at),
    }


@router.post("/raster", status_code=status.HTTP_201_CREATED)
async def upload_raster(
    project_id: int,
    file: UploadFile = File(...),
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _validate_ext(file.filename, RASTER_EXTS, "raster")
    await _get_project_or_404(project_id, db)

    dest = _project_dir(project_id) / file.filename
    saved = _save_upload(file, dest)

    try:
        meta = inspect_raster(saved)
    except Exception as exc:
        saved.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Cannot read raster: {exc}")

    ds = Dataset(
        project_id=project_id,
        name=name or file.filename,
        dataset_type="raster",
        file_path=str(saved),
        metadata_json=meta,
    )
    db.add(ds)
    await db.flush()

    raster = Raster(
        dataset_id=ds.id,
        file_path=str(saved),
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
    await db.refresh(ds)

    logger.info("Uploaded raster %s to project %d", file.filename, project_id)
    return _dataset_response(ds)


@router.post("/vector", status_code=status.HTTP_201_CREATED)
async def upload_vector(
    project_id: int,
    file: UploadFile = File(...),
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _validate_ext(file.filename, VECTOR_EXTS, "vector")
    await _get_project_or_404(project_id, db)

    dest = _project_dir(project_id) / file.filename
    _save_upload(file, dest)

    ds = Dataset(
        project_id=project_id,
        name=name or file.filename,
        dataset_type="vector",
        file_path=str(dest),
        metadata_json={"original_filename": file.filename},
    )
    db.add(ds)
    await db.flush()
    await db.refresh(ds)

    logger.info("Uploaded vector %s to project %d", file.filename, project_id)
    return _dataset_response(ds)


@router.post("/gnss", status_code=status.HTTP_201_CREATED)
async def upload_gnss(
    project_id: int,
    file: UploadFile = File(...),
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _validate_ext(file.filename, GNSS_EXTS, "GNSS")
    await _get_project_or_404(project_id, db)

    dest = _project_dir(project_id) / file.filename
    _save_upload(file, dest)

    ds = Dataset(
        project_id=project_id,
        name=name or file.filename,
        dataset_type="gnss",
        file_path=str(dest),
        metadata_json={"original_filename": file.filename},
    )
    db.add(ds)
    await db.flush()
    await db.refresh(ds)

    logger.info("Uploaded GNSS data %s to project %d", file.filename, project_id)
    return _dataset_response(ds)


@router.post("/{project_id}/all", status_code=status.HTTP_201_CREATED)
async def upload_all(
    project_id: int,
    raster_files: list[UploadFile] = File(default=[]),
    vector_files: list[UploadFile] = File(default=[]),
    gnss_files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_project_or_404(project_id, db)
    results: list[dict] = []

    for f in raster_files:
        _validate_ext(f.filename, RASTER_EXTS, "raster")
        dest = _project_dir(project_id) / f.filename
        saved = _save_upload(f, dest)
        try:
            meta = inspect_raster(saved)
        except Exception:
            continue
        ds = Dataset(project_id=project_id, name=f.filename, dataset_type="raster", file_path=str(saved), metadata_json=meta)
        db.add(ds)
        await db.flush()
        raster = Raster(dataset_id=ds.id, file_path=str(saved), crs=meta.get("crs"), width=meta["width"], height=meta["height"], bands=meta["bands"], resolution=meta["resolution"]["x"], bounds_json=meta["bounds"], nodata=meta.get("nodata"))
        db.add(raster)
        await db.flush()
        await db.refresh(ds)
        results.append(_dataset_response(ds))

    for f in vector_files:
        _validate_ext(f.filename, VECTOR_EXTS, "vector")
        dest = _project_dir(project_id) / f.filename
        _save_upload(f, dest)
        ds = Dataset(project_id=project_id, name=f.filename, dataset_type="vector", file_path=str(dest), metadata_json={"original_filename": f.filename})
        db.add(ds)
        await db.flush()
        await db.refresh(ds)
        results.append(_dataset_response(ds))

    for f in gnss_files:
        _validate_ext(f.filename, GNSS_EXTS, "GNSS")
        dest = _project_dir(project_id) / f.filename
        _save_upload(f, dest)
        ds = Dataset(project_id=project_id, name=f.filename, dataset_type="gnss", file_path=str(dest), metadata_json={"original_filename": f.filename})
        db.add(ds)
        await db.flush()
        await db.refresh(ds)
        results.append(_dataset_response(ds))

    return {"datasets": results, "total": len(results)}
