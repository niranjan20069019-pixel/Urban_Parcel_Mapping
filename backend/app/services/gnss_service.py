from __future__ import annotations

from datetime import datetime

import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, GNSSValidationError
from app.core.logging import get_logger
from app.db.models import GnssPoint, Parcel, Project
from app.gis.distance import point_to_polygon_distance
from app.gis.vector import load_vector

logger = get_logger(__name__)


async def import_gnss_points(
    db: AsyncSession,
    project_id: int,
    file_path: str,
    crs: str,
) -> list[GnssPoint]:
    project = await db.get(Project, project_id)
    if project is None:
        raise AppError(f"Project #{project_id} not found.")

    gdf = load_vector(file_path)
    if gdf.crs is None and crs:
        gdf = gdf.set_crs(crs)

    if str(gdf.crs) != "EPSG:4326" and gdf.crs is not None:
        gdf = gdf.to_crs("EPSG:4326")

    points = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        if geom.geom_type == "Point":
            pt = geom
        elif hasattr(geom, "representative_point"):
            pt = geom.representative_point()
        else:
            continue

        point_id = str(row.get("id", row.get("point_id", f"GNSS_{len(points)}")))
        lat = float(row.get("latitude", row.get("y", pt.y)))
        lon = float(row.get("longitude", row.get("x", pt.x)))
        height_val = row.get("height", row.get("z", None))
        accuracy_val = row.get("accuracy", row.get("precision", None))
        source = row.get("source", "imported")
        ts = row.get("timestamp", row.get("time", None))

        gnss = GnssPoint(
            project_id=project_id,
            point_id=point_id,
            geom=f"SRID=4326;{pt.wkt}",
            latitude=lat,
            longitude=lon,
            height=float(height_val) if height_val is not None else None,
            accuracy=float(accuracy_val) if accuracy_val is not None else None,
            source=str(source),
            crs=crs,
            timestamp=ts if isinstance(ts, datetime) else None,
        )
        db.add(gnss)
        points.append(gnss)

    await db.flush()
    logger.info("Imported %d GNSS points for project %d", len(points), project_id)
    return points


def validate_gnss_accuracy(points: list[GnssPoint], threshold: float) -> dict:
    total = len(points)
    flagged = 0
    flagged_ids = []

    for pt in points:
        if pt.accuracy is not None and pt.accuracy > threshold:
            flagged += 1
            flagged_ids.append(pt.point_id or str(pt.id))

    return {
        "total": total,
        "flagged": flagged,
        "passing": total - flagged,
        "threshold": threshold,
        "flagged_ids": flagged_ids,
    }


def match_gnss_to_parcel(gnss_point: GnssPoint, parcels_gdf: gpd.GeoDataFrame) -> int | None:
    if parcels_gdf is None or parcels_gdf.empty:
        return None

    pt = Point(gnss_point.longitude, gnss_point.latitude)

    for _, row in parcels_gdf.iterrows():
        if row.geometry is not None and not row.geometry.is_empty:
            if row.geometry.contains(pt):
                return int(row.get("id", row.name))

    return None


def calculate_gnss_agreement(
    parcel_id: int,
    gnss_gdf: gpd.GeoDataFrame,
) -> float:
    if gnss_gdf is None or gnss_gdf.empty:
        return 0.5

    distances = []
    for _, pt_row in gnss_gdf.iterrows():
        if pt_row.geometry is None or pt_row.geometry.is_empty:
            continue
        if "parcel_id" in pt_row.index and pt_row["parcel_id"] == parcel_id:
            geom = pt_row.geometry
            if geom.geom_type == "Point":
                distances.append(0.0)
            elif geom.boundary is not None and not geom.boundary.is_empty:
                dist = geom.boundary.distance(Point(0, 0))
                distances.append(dist)

    if not distances:
        return 0.5

    mean_dist = float(np.mean(distances))
    agreement = max(0.0, 1.0 - mean_dist * 1000)
    return min(1.0, agreement)


def transform_gnss_points(points_gdf: gpd.GeoDataFrame, target_crs: str) -> gpd.GeoDataFrame:
    if points_gdf.crs is None:
        raise GNSSValidationError("GeoDataFrame has no CRS set.")
    return points_gdf.to_crs(target_crs)
