from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import Parcel, ParcelChange, Project
from app.schemas.comparison import ChangeType

logger = get_logger(__name__)

router = APIRouter(tags=["comparison"])


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project #{project_id} not found")
    return proj


def _classify_change(iou: float, area_diff: float, centroid_dist: float) -> ChangeType:
    if iou >= 0.9:
        return ChangeType.UNCHANGED
    if area_diff < -0.7 and iou < 0.3:
        return ChangeType.SUBDIVISION
    if area_diff > 1.0 and iou < 0.3:
        return ChangeType.MERGER
    if centroid_dist > 10.0 and iou < 0.3:
        return ChangeType.NEW
    if 0.3 <= iou < 0.9:
        return ChangeType.BOUNDARY_SHIFT
    return ChangeType.UNCERTAIN


def _iou(a, b) -> float:
    if not a.is_valid:
        a = a.buffer(0)
    if not b.is_valid:
        b = b.buffer(0)
    inter = a.intersection(b).area
    union = a.union(b).area
    return inter / union if union > 0 else 0.0


@router.post("/projects/{project_id}/compare")
async def compare_parcels(
    project_id: int,
    old_status: str = "OLD",
    new_status: str = "AI_GENERATED",
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_project_or_404(project_id, db)
    old_status = old_status.upper()
    new_status = new_status.upper()

    old_rows = (await db.execute(
        select(Parcel).where(Parcel.project_id == project_id, Parcel.status == old_status)
    )).scalars().all()
    new_rows = (await db.execute(
        select(Parcel).where(Parcel.project_id == project_id, Parcel.status == new_status)
    )).scalars().all()

    if not old_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No parcels with status '{old_status}'")
    if not new_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No parcels with status '{new_status}'")

    # ponytail: O(n*m) pairwise comparison; spatial index if parcel counts grow large.
    results = []
    compared_new: set[int] = set()

    for old in old_rows:
        old_shape = to_shape(old.geom)
        best = None
        best_score = -1.0
        for new in new_rows:
            new_shape = to_shape(new.geom)
            iou = _iou(old_shape, new_shape)
            if iou > best_score:
                best_score = iou
                best = (new, new_shape)
        if best is None:
            _, new_shape = None, None
        else:
            new, new_shape = best
            compared_new.add(new.id)

        if new is None or new_shape is None:
            change_type = ChangeType.REMOVED
            results.append({
                "old_parcel_id": old.id,
                "new_parcel_id": None,
                "iou": 0.0,
                "area_difference": -1.0,
                "centroid_distance": 0.0,
                "boundary_displacement": 0.0,
                "hausdorff_distance": 0.0,
                "change_type": change_type.value,
            })
            continue

        iou = best_score
        area_diff = (new_shape.area - old_shape.area) / max(old_shape.area, 1e-9)
        centroid_dist = old_shape.centroid.distance(new_shape.centroid)
        change_type = _classify_change(iou, area_diff, centroid_dist)

        results.append({
            "old_parcel_id": old.id,
            "new_parcel_id": new.id,
            "iou": round(iou, 6),
            "area_difference": round(area_diff, 6),
            "centroid_distance": round(centroid_dist, 6),
            "boundary_displacement": round(
                old_shape.exterior.distance(new_shape.exterior) if old_shape.exterior and new_shape.exterior else 0.0, 6
            ),
            "hausdorff_distance": 0.0,
            "change_type": change_type.value,
        })

    for new in new_rows:
        if new.id not in compared_new:
            shape = to_shape(new.geom)
            results.append({
                "old_parcel_id": None,
                "new_parcel_id": new.id,
                "iou": 0.0,
                "area_difference": 1.0,
                "centroid_distance": 0.0,
                "boundary_displacement": 0.0,
                "hausdorff_distance": 0.0,
                "change_type": ChangeType.NEW.value,
            })

    # Persist change records.
    for r in results:
        db.add(ParcelChange(
            project_id=project_id,
            old_parcel_id=r["old_parcel_id"],
            new_parcel_id=r["new_parcel_id"],
            change_type=r["change_type"],
            confidence=None if r["iou"] == 0 else max(r["iou"], 0.1),
        ))
    await db.flush()

    summary = dict(Counter(r["change_type"] for r in results))
    return {"results": results, "summary": {"total": len(results), **summary}}


@router.get("/projects/{project_id}/changes")
async def list_changes(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_project_or_404(project_id, db)
    rows = (await db.execute(
        select(ParcelChange).where(ParcelChange.project_id == project_id).order_by(ParcelChange.id.desc()).offset(skip).limit(limit)
    )).scalars().all()
    return {
        "project_id": project_id,
        "total": len(rows),
        "changes": [
            {
                "id": c.id,
                "old_parcel_id": c.old_parcel_id,
                "new_parcel_id": c.new_parcel_id,
                "change_type": c.change_type,
                "confidence": c.confidence,
                "evidence": c.evidence_json,
                "created_at": str(c.created_at),
            }
            for c in rows
        ],
    }


@router.get("/projects/{project_id}/changes/summary")
async def changes_summary(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    await _get_project_or_404(project_id, db)
    rows = (await db.execute(
        select(ParcelChange).where(ParcelChange.project_id == project_id)
    )).scalars().all()
    counts = Counter(c.change_type for c in rows)
    high_confidence = sum(1 for c in rows if (c.confidence or 0) >= 0.8)
    return {
        "project_id": project_id,
        "total_changes": len(rows),
        "by_type": dict(counts),
        "high_confidence_count": high_confidence,
        "needs_review": high_confidence and len(rows) - high_confidence,
    }