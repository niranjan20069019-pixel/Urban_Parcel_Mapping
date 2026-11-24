from __future__ import annotations

import csv
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import wkt as shapely_wkt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, ExportError
from app.core.logging import get_logger
from app.db.models import (
    Building,
    BoundaryEvidence,
    Dataset,
    LanduseFeature,
    Parcel,
    ParcelChange,
    ParcelStatus,
    Project,
    Road,
    Recommendation,
)

logger = get_logger(__name__)

_FORMAT_DRIVERS = {
    "geojson": "GeoJSON",
    "gpkg": "GPKG",
    "geopackage": "GPKG",
    "shp": "ESRI Shapefile",
    "shapefile": "ESRI Shapefile",
}

_FORMAT_EXTENSIONS = {
    "geojson": ".geojson",
    "gpkg": ".gpkg",
    "geopackage": ".gpkg",
    "shp": ".shp",
    "shapefile": ".shp",
    "csv": ".csv",
}


def _resolve_driver(fmt: str) -> str:
    return _FORMAT_DRIVERS.get(fmt.lower(), "GeoJSON")


def _resolve_ext(fmt: str) -> str:
    return _FORMAT_EXTENSIONS.get(fmt.lower(), ".geojson")


def _output_path(project_id: int, name: str, fmt: str) -> Path:
    out = settings.DATA_DIR / f"project_{project_id}" / "exports"
    out.mkdir(parents=True, exist_ok=True)
    return out / f"{name}{_resolve_ext(fmt)}"


def _parcels_to_gdf(parcels: list[Parcel]) -> gpd.GeoDataFrame:
    records = []
    for p in parcels:
        geom_wkt = p.geom
        if geom_wkt and geom_wkt.startswith("SRID=4326;"):
            geom_wkt = geom_wkt.replace("SRID=4326;", "")
        geom = shapely_wkt.loads(geom_wkt) if geom_wkt else None
        records.append({
            "parcel_id": p.id,
            "version": p.version,
            "status": p.status.value if isinstance(p.status, ParcelStatus) else p.status,
            "area": p.area,
            "perimeter": p.perimeter,
            "confidence": p.confidence,
            "change_type": p.change_type,
            "parent_parcel_id": p.parent_parcel_id,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "geometry": geom,
        })
    if not records:
        return gpd.GeoDataFrame(columns=["parcel_id", "geometry"], crs="EPSG:4326")
    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def _features_to_gdf(features: list, geom_col: str = "geom") -> gpd.GeoDataFrame:
    records = []
    for f in features:
        geom_wkt = getattr(f, geom_col, None)
        if geom_wkt and isinstance(geom_wkt, str) and geom_wkt.startswith("SRID=4326;"):
            geom_wkt = geom_wkt.replace("SRID=4326;", "")
        geom = shapely_wkt.loads(geom_wkt) if geom_wkt and isinstance(geom_wkt, str) else geom_wkt
        record = {"geometry": geom}
        for col in f.__table__.columns:
            if col.name not in ("geom", "id", "created_at", "updated_at"):
                record[col.name] = getattr(f, col.name)
        records.append(record)
    if not records:
        return gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
    return gpd.GeoDataFrame(records, crs="EPSG:4326")


async def export_parcels(
    db: AsyncSession,
    project_id: int,
    fmt: str = "geojson",
    status_filter: str | None = None,
) -> str:
    stmt = select(Parcel).where(Parcel.project_id == project_id)
    if status_filter:
        stmt = stmt.where(Parcel.status == ParcelStatus(status_filter))
    result = await db.execute(stmt)
    parcels = list(result.scalars().all())

    if not parcels:
        raise ExportError(f"No parcels to export for project #{project_id}.")

    gdf = _parcels_to_gdf(parcels)

    if fmt.lower() == "csv":
        return await _export_csv(db, project_id, gdf)

    path = _output_path(project_id, f"parcels_{status_filter or 'all'}", fmt)
    driver = _resolve_driver(fmt)
    gdf.to_file(str(path), driver=driver)
    logger.info("Exported %d parcels to %s", len(parcels), path)
    return str(path)


async def export_features(
    db: AsyncSession,
    project_id: int,
    feature_type: str,
    fmt: str = "geojson",
) -> str:
    model_map = {
        "buildings": Building,
        "roads": Road,
        "landuse": LanduseFeature,
        "boundary": BoundaryEvidence,
    }
    model = model_map.get(feature_type)
    if model is None:
        raise ExportError(f"Unknown feature type: {feature_type}")

    stmt = select(model).where(model.project_id == project_id)
    result = await db.execute(stmt)
    features = list(result.scalars().all())

    if not features:
        raise ExportError(f"No {feature_type} features to export for project #{project_id}.")

    gdf = _features_to_gdf(features)

    if fmt.lower() == "csv":
        return await _export_csv(db, project_id, gdf)

    path = _output_path(project_id, feature_type, fmt)
    driver = _resolve_driver(fmt)
    gdf.to_file(str(path), driver=driver)
    logger.info("Exported %d %s features to %s", len(features), feature_type, path)
    return str(path)


async def export_full_project(
    db: AsyncSession,
    project_id: int,
    fmt: str = "geojson",
) -> dict[str, str]:
    paths = {}
    try:
        paths["parcels"] = await export_parcels(db, project_id, fmt)
    except ExportError:
        paths["parcels"] = None

    for ftype in ["buildings", "roads", "landuse", "boundary"]:
        try:
            paths[ftype] = await export_features(db, project_id, ftype, fmt)
        except ExportError:
            paths[ftype] = None

    return paths


async def _export_csv(db: AsyncSession, project_id: int, gdf: gpd.GeoDataFrame) -> str:
    path = _output_path(project_id, "export", "csv")
    df = pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))
    if "geometry" in gdf.columns:
        df["geometry_wkt"] = gdf.geometry.to_wkt()
    df.to_csv(str(path), index=False)
    logger.info("Exported CSV to %s", path)
    return str(path)


async def export_attributes_csv(db: AsyncSession, project_id: int) -> str:
    stmt = select(Parcel).where(Parcel.project_id == project_id)
    result = await db.execute(stmt)
    parcels = list(result.scalars().all())

    if not parcels:
        raise ExportError(f"No parcels for project #{project_id}.")

    path = _output_path(project_id, "parcel_attributes", "csv")
    with open(str(path), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "parcel_id", "version", "status", "area", "perimeter",
            "confidence", "change_type", "parent_parcel_id", "geometry_wkt",
        ])
        for p in parcels:
            geom_wkt = p.geom.replace("SRID=4326;", "") if p.geom else ""
            writer.writerow([
                p.id,
                p.version,
                p.status.value if isinstance(p.status, ParcelStatus) else p.status,
                p.area,
                p.perimeter,
                p.confidence,
                p.change_type,
                p.parent_parcel_id,
                geom_wkt,
            ])

    logger.info("Exported attributes CSV for %d parcels to %s", len(parcels), path)
    return str(path)
