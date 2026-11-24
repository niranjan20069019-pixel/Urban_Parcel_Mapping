from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import GnssPoint, Parcel, Project
from app.schemas.gnss import GnssPointResponse

logger = get_logger(__name__)

router = APIRouter(tags=["gnss"])


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project #{project_id} not found")
    return proj


def _to_response(p: GnssPoint) -> GnssPointResponse:
    return GnssPointResponse(
        id=p.id,
        point_id=p.point_id or str(p.id),
        latitude=p.latitude,
        longitude=p.longitude,
        height=p.height,
        accuracy=p.accuracy,
        crs=p.crs or "EPSG:4326",
        source=p.source,
        created_at=p.created_at,
    )


async def _project_points(project_id: int, db: AsyncSession) -> list[GnssPoint]:
    return (await db.execute(
        select(GnssPoint).where(GnssPoint.project_id == project_id).order_by(GnssPoint.id)
    )).scalars().all()


@router.get("/projects/{project_id}/gnss/points", response_model=list[GnssPointResponse])
async def list_gnss_points(
    project_id: int,
    limit: int = Query(1000, le=10000),
    db: AsyncSession = Depends(get_db),
) -> list[GnssPointResponse]:
    await _get_project_or_404(project_id, db)
    rows = (await db.execute(
        select(GnssPoint).where(GnssPoint.project_id == project_id).order_by(GnssPoint.id).limit(limit)
    )).scalars().all()
    return [_to_response(p) for p in rows]


@router.post("/projects/{project_id}/gnss/validate")
async def validate_gnss(
    project_id: int,
    tolerance_m: float = Query(5.0, description="Max distance in metres to a parcel boundary"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_project_or_404(project_id, db)
    points = await _project_points(project_id, db)
    parcels = (await db.execute(select(Parcel).where(Parcel.project_id == project_id))).scalars().all()
    if not points:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No GNSS points found for project #{project_id}")
    if not parcels:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No parcels found for project #{project_id}")

    parcel_shapes = [to_shape(p.geom) for p in parcels]
    results = []
    inside_count = 0
    for pt in points:
        point_shape = to_shape(pt.geom)
        parcel_found = None
        min_dist = float("inf")
        for parcel, shape in zip(parcels, parcel_shapes):
            if shape.contains(point_shape):
                parcel_found = parcel
                break
            dist = shape.distance(point_shape)
            min_dist = min(min_dist, dist)
        if parcel_found is not None:
            inside_count += 1
            results.append({
                "point_id": pt.point_id or str(pt.id),
                "nearest_parcel_id": parcel_found.id,
                "distance_to_boundary": 0.0,
                "accuracy_flag": (pt.accuracy or tolerance_m) <= tolerance_m,
                "location": "inside_parcel",
            })
        else:
            results.append({
                "point_id": pt.point_id or str(pt.id),
                "nearest_parcel_id": None,
                "distance_to_boundary": round(min_dist, 6),
                "accuracy_flag": (pt.accuracy or tolerance_m) <= tolerance_m,
                "location": "outside",
            })

    return {
        "project_id": project_id,
        "total_points": len(points),
        "inside_parcels": inside_count,
        "outside_parcels": len(points) - inside_count,
        "tolerance_m": tolerance_m,
        "results": results,
    }


@router.post("/projects/{project_id}/gnss/match")
async def match_gnss_to_parcels(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_project_or_404(project_id, db)
    points = await _project_points(project_id, db)
    parcels = (await db.execute(select(Parcel).where(Parcel.project_id == project_id))).scalars().all()
    if not points:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No GNSS points found for project #{project_id}")
    if not parcels:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No parcels found for project #{project_id}")

    parcel_shapes = [(p, to_shape(p.geom)) for p in parcels]
    matches: list[dict] = []
    matched_parcel_ids: set[int] = set()

    for pt in points:
        point_shape = to_shape(pt.geom)
        best_parcel, best_dist = None, float("inf")
        for parcel, shape in parcel_shapes:
            if shape.contains(point_shape):
                best_parcel, best_dist = parcel, 0.0
                break
            dist = shape.distance(point_shape)
            if dist < best_dist:
                best_parcel, best_dist = parcel, dist
        if best_parcel is not None:
            matched_parcel_ids.add(best_parcel.id)
        matches.append({
            "point_id": pt.point_id or str(pt.id),
            "parcel_id": best_parcel.id if best_parcel else None,
            "distance": round(best_dist, 6),
            "matched": best_parcel is not None,
        })

    # Mark parcels touched by GNSS points as GNSS_VALIDATED.
    for parcel_id in matched_parcel_ids:
        parcel = await db.get(Parcel, parcel_id)
        if parcel is not None:
            from app.db.models import ParcelStatus, Validation

            parcel.status = ParcelStatus.GNSS_VALIDATED
            db.add(Validation(
                parcel_id=parcel_id,
                validator="gnss",
                validation_type="gnss_match",
                status="matched",
                notes="Parcel matched by GNSS point",
            ))
    await db.flush()

    return {
        "project_id": project_id,
        "points_total": len(points),
        "points_matched": sum(1 for m in matches if m["matched"]),
        "parcels_matched": len(matched_parcel_ids),
        "matches": matches,
    }