from __future__ import annotations

import io
import json
import zipfile

import geopandas as gpd
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import (
    BoundaryEvidence,
    Building,
    Dataset,
    LanduseFeature,
    Parcel,
    Project,
    Road,
)

logger = get_logger(__name__)

router = APIRouter(tags=["export"])

FEATURE_EXPORTS = {
    "buildings": Building,
    "roads": Road,
    "landuse": LanduseFeature,
    "boundaries": BoundaryEvidence,
}


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project #{project_id} not found")
    return proj


def _parcel_gdf(rows: list[Parcel]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "id": [p.id for p in rows],
            "version": [p.version for p in rows],
            "status": [p.status.name for p in rows],
            "area": [p.area for p in rows],
            "perimeter": [p.perimeter for p in rows],
            "confidence": [p.confidence for p in rows],
            "change_type": [p.change_type for p in rows],
            "metadata": [json.dumps(p.metadata_json) if p.metadata_json else None for p in rows],
        },
        geometry=[to_shape(p.geom) for p in rows],
        crs="EPSG:4326",
    )


def _feature_gdf(model, rows) -> gpd.GeoDataFrame:
    data: dict = {}
    for col in model.__table__.columns:
        if col.name in ("geom", "prediction_id", "id", "created_at", "updated_at"):
            continue
        if col.type.__class__.__name__ == "Geometry":
            continue
        data[col.name] = [getattr(r, col.name) for r in rows]
    return gpd.GeoDataFrame(
        data,
        geometry=[to_shape(r.geom) for r in rows],
        crs="EPSG:4326",
    )


def _geojson_bytes(gdf: gpd.GeoDataFrame) -> bytes:
    return gdf.to_json().encode("utf-8")


def _csv_bytes(gdf: gpd.GeoDataFrame) -> bytes:
    out = io.StringIO()
    gdf.drop(columns=["geometry"], errors="ignore").to_csv(out, index=False)
    return out.getvalue().encode("utf-8")


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, default=str).encode("utf-8")


def _zip_bytes(files: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files:
            zf.writestr(name, content)
    return buf.getvalue()


@router.get("/projects/{project_id}/export/parcels")
async def export_parcels(
    project_id: int,
    format: str = Query("geojson", pattern="^(geojson|csv)$"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _get_project_or_404(project_id, db)
    rows = (await db.execute(select(Parcel).where(Parcel.project_id == project_id).order_by(Parcel.id))).scalars().all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No parcels for project #{project_id}")
    gdf = _parcel_gdf(rows)

    if format == "csv":
        content = _csv_bytes(gdf)
        media_type = "text/csv"
        filename = f"parcels_{project_id}.csv"
    else:
        content = _geojson_bytes(gdf)
        media_type = "application/geo+json"
        filename = f"parcels_{project_id}.geojson"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/export/features/{feature_type}")
async def export_features(
    project_id: int,
    feature_type: str,
    format: str = Query("geojson", pattern="^(geojson|csv)$"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _get_project_or_404(project_id, db)
    model = FEATURE_EXPORTS.get(feature_type)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown feature type '{feature_type}'. Supported: {sorted(FEATURE_EXPORTS)}")
    rows = (await db.execute(select(model).where(model.project_id == project_id))).scalars().all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No {feature_type} for project #{project_id}")
    gdf = _feature_gdf(model, rows)

    if format == "csv":
        content = _csv_bytes(gdf)
        media_type = "text/csv"
        filename = f"{feature_type}_{project_id}.csv"
    else:
        content = _geojson_bytes(gdf)
        media_type = "application/geo+json"
        filename = f"{feature_type}_{project_id}.geojson"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/export/csv")
async def export_attributes_csv(project_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    await _get_project_or_404(project_id, db)
    rows = (await db.execute(select(Parcel).where(Parcel.project_id == project_id))).scalars().all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No parcels for project #{project_id}")
    gdf = _parcel_gdf(rows).drop(columns=["geometry"])
    csv = gdf.to_csv(index=False)
    return Response(
        content=csv.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="parcel_attributes_{project_id}.csv"'},
    )


@router.get("/projects/{project_id}/export/full")
async def export_full(project_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    await _get_project_or_404(project_id, db)
    files: list[tuple[str, bytes]] = []

    parcels = (await db.execute(select(Parcel).where(Parcel.project_id == project_id))).scalars().all()
    if parcels:
        files.append((f"parcels_{project_id}.geojson", _geojson_bytes(_parcel_gdf(parcels))))

    datasets = (await db.execute(select(Dataset).where(Dataset.project_id == project_id))).scalars().all()
    files.append((
        f"datasets_{project_id}.json",
        _json_bytes([{k: v for k, v in ds.__dict__.items() if not k.startswith("_")} for ds in datasets]),
    ))

    for feature_type, model in FEATURE_EXPORTS.items():
        rows = (await db.execute(select(model).where(model.project_id == project_id))).scalars().all()
        if rows:
            files.append((f"{feature_type}_{project_id}.geojson", _geojson_bytes(_feature_gdf(model, rows))))

    return Response(
        content=_zip_bytes(files),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="export_{project_id}.zip"'},
    )