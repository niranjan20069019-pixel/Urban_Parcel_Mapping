from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Parcel, ParcelStatus, TopologyIssue
from app.gis.distance import centroid_distance, hausdorff_distance, polygon_iou

logger = get_logger(__name__)

_DEFAULT_WEIGHTS = {
    "ai_agreement": 0.25,
    "gis_agreement": 0.20,
    "boundary_evidence": 0.15,
    "gnss_agreement": 0.20,
    "topology_validity": 0.10,
    "area_plausibility": 0.10,
}


@dataclass
class ConfidenceFactor:
    name: str
    score: float
    weight: float
    details: dict | None = None


async def _get_topology_score(db: AsyncSession, project_id: int) -> float:
    result = await db.execute(
        select(TopologyIssue).where(
            TopologyIssue.project_id == project_id,
            TopologyIssue.resolved == False,
        )
    )
    issues = list(result.scalars().all())
    if not issues:
        return 1.0

    high = sum(1 for i in issues if i.severity == "HIGH")
    med = sum(1 for i in issues if i.severity == "MEDIUM")
    penalty = high * 0.15 + med * 0.05
    return max(0.0, 1.0 - penalty)


async def calculate_parcel_confidence(
    db: AsyncSession,
    parcel_id: int,
) -> float:
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None:
        return 0.0

    factors = await get_confidence_breakdown(db, parcel_id)
    return sum(f.score * f.weight for f in factors)


async def calculate_batch_confidence(
    db: AsyncSession,
    parcel_ids: list[int],
) -> dict[int, float]:
    results = {}
    for pid in parcel_ids:
        results[pid] = await calculate_parcel_confidence(db, pid)
    return results


async def get_confidence_breakdown(
    db: AsyncSession,
    parcel_id: int,
) -> list[ConfidenceFactor]:
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None:
        return []

    ai_score = 0.5
    if parcel.status == ParcelStatus.AI_GENERATED:
        ai_score = 0.8
    elif parcel.status == ParcelStatus.GNSS_VALIDATED:
        ai_score = 0.9
    elif parcel.status == ParcelStatus.FINAL_VALIDATED:
        ai_score = 1.0
    elif parcel.status == ParcelStatus.SURVEYOR_EDITED:
        ai_score = 0.85
    elif parcel.status == ParcelStatus.OLD:
        ai_score = 0.6

    gis_score = 0.7
    if parcel.area and parcel.area > 0:
        gis_score = 0.9
    if parcel.perimeter and parcel.perimeter > 0:
        gis_score = min(1.0, gis_score + 0.05)

    boundary_score = 0.5
    gnss_score = 0.5
    if parcel.status == ParcelStatus.GNSS_VALIDATED or parcel.status == ParcelStatus.FINAL_VALIDATED:
        gnss_score = 0.95
        boundary_score = 0.8

    topology_score = await _get_topology_score(db, parcel.project_id)

    area_score = 0.5
    if parcel.area:
        if 100 < parcel.area < 100000:
            area_score = 0.9
        elif 10 < parcel.area < 1000000:
            area_score = 0.7
        else:
            area_score = 0.3

    factors = [
        ConfidenceFactor(name="ai_agreement", score=ai_score, weight=_DEFAULT_WEIGHTS["ai_agreement"]),
        ConfidenceFactor(name="gis_agreement", score=gis_score, weight=_DEFAULT_WEIGHTS["gis_agreement"]),
        ConfidenceFactor(name="boundary_evidence", score=boundary_score, weight=_DEFAULT_WEIGHTS["boundary_evidence"]),
        ConfidenceFactor(name="gnss_agreement", score=gnss_score, weight=_DEFAULT_WEIGHTS["gnss_agreement"]),
        ConfidenceFactor(name="topology_validity", score=topology_score, weight=_DEFAULT_WEIGHTS["topology_validity"]),
        ConfidenceFactor(name="area_plausibility", score=area_score, weight=_DEFAULT_WEIGHTS["area_plausibility"]),
    ]

    return factors
