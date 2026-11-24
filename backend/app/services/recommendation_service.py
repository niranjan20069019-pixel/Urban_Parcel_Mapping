from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Parcel, ParcelChange, ParcelStatus, Recommendation, TopologyIssue

logger = get_logger(__name__)


async def generate_recommendations(db: AsyncSession, project_id: int) -> list[dict]:
    result = await db.execute(
        select(Parcel).where(Parcel.project_id == project_id)
    )
    parcels = list(result.scalars().all())

    topo_result = await db.execute(
        select(TopologyIssue).where(
            TopologyIssue.project_id == project_id,
            TopologyIssue.resolved == False,
        )
    )
    topology_issues = list(topo_result.scalars().all())
    topo_parcels = {issue.parcel_id for issue in topology_issues if issue.parcel_id}

    change_result = await db.execute(
        select(ParcelChange).where(ParcelChange.project_id == project_id)
    )
    changes = list(change_result.scalars().all())
    change_map: dict[int, list[ParcelChange]] = {}
    for ch in changes:
        if ch.old_parcel_id:
            change_map.setdefault(ch.old_parcel_id, []).append(ch)
        if ch.new_parcel_id:
            change_map.setdefault(ch.new_parcel_id, []).append(ch)

    recs = []
    for parcel in parcels:
        pid = parcel.id
        conf = parcel.confidence or 0.0
        status = parcel.status if isinstance(parcel.status, ParcelStatus) else ParcelStatus(parcel.status)

        has_topo_issue = pid in topo_parcels
        parcel_changes = change_map.get(pid, [])

        if has_topo_issue:
            recs.append({
                "parcel_id": pid,
                "action": "TOPOLOGY_REPAIR",
                "priority": "HIGH",
                "reason": "Topology issue detected for this parcel",
                "evidence": {"topology_issue": True},
            })

        for ch in parcel_changes:
            if ch.change_type == "SUBDIVISION":
                recs.append({
                    "parcel_id": pid,
                    "action": "INVESTIGATE_SUBDIVISION",
                    "priority": "MEDIUM",
                    "reason": "Subdivision detected in change analysis",
                    "evidence": {"change_type": "SUBDIVISION", "confidence": ch.confidence},
                })
            elif ch.change_type == "MERGER":
                recs.append({
                    "parcel_id": pid,
                    "action": "INVESTIGATE_MERGER",
                    "priority": "MEDIUM",
                    "reason": "Merger detected in change analysis",
                    "evidence": {"change_type": "MERGER", "confidence": ch.confidence},
                })
            elif ch.change_type == "NEW":
                recs.append({
                    "parcel_id": pid,
                    "action": "INVESTIGATE_NEW_PARCEL",
                    "priority": "MEDIUM",
                    "reason": "New parcel detected",
                    "evidence": {"change_type": "NEW", "confidence": ch.confidence},
                })
            elif ch.change_type == "CONFLICT":
                recs.append({
                    "parcel_id": pid,
                    "action": "FIELD_SURVEY",
                    "priority": "HIGH",
                    "reason": "Conflict detected between old and new boundaries",
                    "evidence": {"change_type": "CONFLICT", "confidence": ch.confidence},
                })

        if conf < 0.5 and not has_topo_issue:
            recs.append({
                "parcel_id": pid,
                "action": "SURVEYOR_REVIEW",
                "priority": "HIGH",
                "reason": f"Low confidence score ({conf:.2f})",
                "evidence": {"confidence": conf},
            })
        elif 0.5 <= conf < 0.7 and not has_topo_issue:
            recs.append({
                "parcel_id": pid,
                "action": "SURVEYOR_REVIEW",
                "priority": "MEDIUM",
                "reason": f"Moderate confidence score ({conf:.2f})",
                "evidence": {"confidence": conf},
            })
        elif conf >= 0.7 and status in (ParcelStatus.AI_GENERATED,) and not has_topo_issue:
            recs.append({
                "parcel_id": pid,
                "action": "ACCEPT_PRELIMINARY",
                "priority": "LOW",
                "reason": f"High confidence ({conf:.2f}), valid topology",
                "evidence": {"confidence": conf},
            })

    for rec in recs:
        db_rec = Recommendation(
            parcel_id=rec["parcel_id"],
            action=rec["action"],
            priority=rec["priority"],
            reason=rec["reason"],
            evidence_json=rec.get("evidence"),
        )
        db.add(db_rec)

    await db.flush()
    logger.info("Generated %d recommendations for project %d", len(recs), project_id)
    return recs
