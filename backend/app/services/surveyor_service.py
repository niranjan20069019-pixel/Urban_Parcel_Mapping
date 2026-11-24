from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.models import (
    Parcel,
    ParcelStatus,
    Recommendation,
    SurveyorEdit,
    Validation,
)
from app.gis.geometry import compute_area_km2, compute_perimeter_km

logger = get_logger(__name__)


async def _get_parcel(db: AsyncSession, parcel_id: int) -> Parcel:
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None:
        raise AppError(f"Parcel #{parcel_id} not found.")
    return parcel


async def get_parcels_for_review(db: AsyncSession, project_id: int) -> list[dict]:
    stmt = (
        select(Parcel, Recommendation)
        .join(Recommendation, Recommendation.parcel_id == Parcel.id)
        .where(Parcel.project_id == project_id)
        .where(Recommendation.acknowledged_at.is_(None))
        .order_by(
            func.case(
                (Recommendation.priority == "HIGH", 0),
                (Recommendation.priority == "MEDIUM", 1),
                else_=2,
            )
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    parcels_with_recs = []
    for parcel, rec in rows:
        parcels_with_recs.append({
            "parcel_id": parcel.id,
            "version": parcel.version,
            "status": parcel.status.value if isinstance(parcel.status, ParcelStatus) else parcel.status,
            "confidence": parcel.confidence,
            "area": parcel.area,
            "recommendation": {
                "id": rec.id,
                "action": rec.action,
                "priority": rec.priority,
                "reason": rec.reason,
            },
        })

    return parcels_with_recs


async def submit_edit(
    db: AsyncSession,
    parcel_id: int,
    new_geom,
    editor: str,
    notes: str | None = None,
) -> Parcel:
    parcel = await _get_parcel(db, parcel_id)

    if isinstance(new_geom, str):
        new_geom_wkt = new_geom
    else:
        new_geom_wkt = f"SRID=4326;{new_geom.wkt}"

    edit = SurveyorEdit(
        parcel_id=parcel_id,
        editor=editor,
        old_geom=parcel.geom,
        new_geom=new_geom_wkt,
        notes=notes,
    )
    db.add(edit)

    from shapely import wkt as shapely_wkt
    geom_clean = new_geom_wkt.replace("SRID=4326;", "")
    geom = shapely_wkt.loads(geom_clean)
    area = compute_area_km2(geom)
    perimeter = compute_perimeter_km(geom)

    parcel.geom = new_geom_wkt
    parcel.area = area
    parcel.perimeter = perimeter
    parcel.centroid = f"SRID=4326;{geom.centroid.wkt}"
    parcel.version += 1
    parcel.status = ParcelStatus.SURVEYOR_EDITED

    await db.flush()
    await db.refresh(parcel)
    logger.info("Surveyor %s edited parcel %d -> version %d", editor, parcel_id, parcel.version)
    return parcel


async def accept_parcel(db: AsyncSession, parcel_id: int, editor: str) -> Parcel:
    parcel = await _get_parcel(db, parcel_id)
    parcel.status = ParcelStatus.FINAL_VALIDATED

    val = Validation(
        parcel_id=parcel_id,
        validator=editor,
        validation_type="acceptance",
        status="ACCEPTED",
    )
    db.add(val)
    await db.flush()
    await db.refresh(parcel)
    logger.info("Parcel %d accepted by %s", parcel_id, editor)
    return parcel


async def reject_parcel(
    db: AsyncSession,
    parcel_id: int,
    editor: str,
    reason: str | None = None,
) -> Parcel:
    parcel = await _get_parcel(db, parcel_id)
    parcel.status = ParcelStatus.AI_GENERATED

    val = Validation(
        parcel_id=parcel_id,
        validator=editor,
        validation_type="rejection",
        status="REJECTED",
        notes=reason,
    )
    db.add(val)
    await db.flush()
    await db.refresh(parcel)
    logger.info("Parcel %d rejected by %s: %s", parcel_id, editor, reason)
    return parcel


async def mark_field_verification(db: AsyncSession, parcel_id: int, editor: str) -> Parcel:
    parcel = await _get_parcel(db, parcel_id)
    parcel.status = ParcelStatus.GNSS_VALIDATED

    val = Validation(
        parcel_id=parcel_id,
        validator=editor,
        validation_type="field_verification",
        status="FIELD_VERIFIED",
    )
    db.add(val)
    await db.flush()
    await db.refresh(parcel)
    logger.info("Parcel %d marked as field-verified by %s", parcel_id, editor)
    return parcel


async def add_note(
    db: AsyncSession,
    parcel_id: int,
    editor: str,
    note: str,
) -> dict:
    parcel = await _get_parcel(db, parcel_id)

    val = Validation(
        parcel_id=parcel_id,
        validator=editor,
        validation_type="note",
        notes=note,
    )
    db.add(val)
    await db.flush()

    return {
        "parcel_id": parcel_id,
        "editor": editor,
        "note": note,
        "validation_id": val.id,
    }


async def get_surveyor_stats(db: AsyncSession, project_id: int) -> dict:
    stmt = select(Parcel).where(Parcel.project_id == project_id)
    result = await db.execute(stmt)
    parcels = list(result.scalars().all())

    accepted = sum(
        1 for p in parcels
        if (p.status if isinstance(p.status, ParcelStatus) else ParcelStatus(p.status)) == ParcelStatus.FINAL_VALIDATED
    )
    rejected = sum(
        1 for p in parcels
        if (p.status if isinstance(p.status, ParcelStatus) else ParcelStatus(p.status)) == ParcelStatus.SURVEYOR_EDITED
    )
    pending = sum(
        1 for p in parcels
        if (p.status if isinstance(p.status, ParcelStatus) else ParcelStatus(p.status)) in (ParcelStatus.AI_GENERATED,)
    )

    return {
        "total": len(parcels),
        "accepted": accepted,
        "rejected": rejected,
        "pending": pending,
    }
