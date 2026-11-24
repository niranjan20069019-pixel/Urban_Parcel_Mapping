from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping as shapely_mapping, shape as shapely_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import (
    Parcel,
    ParcelStatus,
    Project,
    SurveyorEdit,
    Validation,
)
from app.schemas.parcels import ParcelEditRequest, ParcelResponse

logger = get_logger(__name__)

router = APIRouter(tags=["surveyor"])

REVIEW_STATUSES = {"AI_GENERATED", "SURVEYOR_EDITED"}


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project #{project_id} not found")
    return proj


def _to_response(p: Parcel) -> ParcelResponse:
    return ParcelResponse(
        id=p.id,
        project_id=p.project_id,
        version=p.version,
        status=p.status.name.lower(),
        area=p.area or 0.0,
        perimeter=p.perimeter or 0.0,
        confidence=p.confidence or 0.0,
        change_type=p.change_type,
        geom_json=shapely_mapping(to_shape(p.geom)),
        metadata=p.metadata_json,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/projects/{project_id}/surveyor/queue", response_model=list[ParcelResponse])
async def review_queue(
    project_id: int,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[ParcelResponse]:
    await _get_project_or_404(project_id, db)
    stmt = select(Parcel).where(Parcel.project_id == project_id)
    if status_filter:
        normalized = status_filter.upper()
        if normalized not in {s.name for s in ParcelStatus}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status '{status_filter}'. Valid: {sorted(s.name for s in ParcelStatus)}",
            )
        stmt = stmt.where(Parcel.status == normalized)
    else:
        stmt = stmt.where(Parcel.status.in_(REVIEW_STATUSES))
    stmt = stmt.order_by(Parcel.confidence.asc().nullslast(), Parcel.id)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(p) for p in rows]


@router.post("/projects/{project_id}/surveyor/{parcel_id}/edit", response_model=ParcelResponse)
async def surveyor_edit(
    project_id: int,
    parcel_id: int,
    body: ParcelEditRequest,
    db: AsyncSession = Depends(get_db),
) -> ParcelResponse:
    await _get_project_or_404(project_id, db)
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None or parcel.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel #{parcel_id} not found in project #{project_id}")

    new_shape = shapely_shape(body.geom_json)
    if not new_shape.is_valid:
        new_shape = new_shape.buffer(0)

    parcel.surveyor_edits.append(SurveyorEdit(
        parcel_id=parcel.id,
        editor=body.editor,
        old_geom=WKTElement(to_shape(parcel.geom).wkt, srid=4326),
        new_geom=WKTElement(new_shape.wkt, srid=4326),
        notes=body.notes,
    ))
    parcel.geom = WKTElement(new_shape.wkt, srid=4326)
    parcel.area = new_shape.area
    parcel.perimeter = new_shape.length
    parcel.centroid = WKTElement(new_shape.centroid.wkt, srid=4326)
    parcel.status = ParcelStatus.SURVEYOR_EDITED
    await db.flush()
    await db.refresh(parcel)
    return _to_response(parcel)


@router.post("/projects/{project_id}/surveyor/{parcel_id}/accept", response_model=ParcelResponse)
async def surveyor_accept(
    project_id: int,
    parcel_id: int,
    editor: str = "surveyor",
    db: AsyncSession = Depends(get_db),
) -> ParcelResponse:
    await _get_project_or_404(project_id, db)
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None or parcel.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel #{parcel_id} not found in project #{project_id}")
    parcel.status = ParcelStatus.FINAL_VALIDATED
    db.add(Validation(
        parcel_id=parcel_id,
        validator=editor,
        validation_type="surveyor_review",
        status="accepted",
        notes="Accepted by surveyor",
    ))
    await db.flush()
    await db.refresh(parcel)
    return _to_response(parcel)


@router.post("/projects/{project_id}/surveyor/{parcel_id}/reject", response_model=ParcelResponse)
async def surveyor_reject(
    project_id: int,
    parcel_id: int,
    reason: str = "",
    editor: str = "surveyor",
    db: AsyncSession = Depends(get_db),
) -> ParcelResponse:
    await _get_project_or_404(project_id, db)
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None or parcel.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel #{parcel_id} not found in project #{project_id}")
    parcel.status = ParcelStatus.AI_GENERATED
    db.add(Validation(
        parcel_id=parcel_id,
        validator=editor,
        validation_type="surveyor_review",
        status="rejected",
        notes=reason or "Rejected by surveyor",
    ))
    await db.flush()
    await db.refresh(parcel)
    return _to_response(parcel)


@router.post("/projects/{project_id}/surveyor/{parcel_id}/field-verify", response_model=ParcelResponse)
async def surveyor_field_verify(
    project_id: int,
    parcel_id: int,
    editor: str = "surveyor",
    db: AsyncSession = Depends(get_db),
) -> ParcelResponse:
    await _get_project_or_404(project_id, db)
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None or parcel.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel #{parcel_id} not found in project #{project_id}")
    db.add(Validation(
        parcel_id=parcel_id,
        validator=editor,
        validation_type="field_verification",
        status="pending",
        notes="Marked for field verification",
    ))
    metadata = dict(parcel.metadata_json or {})
    metadata["field_verification"] = "required"
    metadata["field_verification_by"] = editor
    parcel.metadata_json = metadata
    await db.flush()
    await db.refresh(parcel)
    return _to_response(parcel)


@router.get("/projects/{project_id}/surveyor/stats")
async def surveyor_stats(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    await _get_project_or_404(project_id, db)
    parcels = (await db.execute(select(Parcel).where(Parcel.project_id == project_id))).scalars().all()
    status_counts = Counter(p.status.name for p in parcels)

    validations = (await db.execute(
        select(Validation).join(Parcel, Parcel.id == Validation.parcel_id).where(Parcel.project_id == project_id)
    )).scalars().all()
    validation_status = Counter(v.status for v in validations)

    edit_count = (await db.execute(
        select(SurveyorEdit).join(Parcel, Parcel.id == SurveyorEdit.parcel_id).where(Parcel.project_id == project_id)
    )).scalars().all()

    return {
        "project_id": project_id,
        "total_parcels": len(parcels),
        "parcel_statuses": dict(status_counts),
        "pending_review": sum(status_counts[s] for s in REVIEW_STATUSES if s in status_counts),
        "validated": status_counts.get("FINAL_VALIDATED", 0),
        "gnss_validated": status_counts.get("GNSS_VALIDATED", 0),
        "validations_by_status": dict(validation_status),
        "surveyor_edits": len(edit_count),
        "edits_by_surveyor": {
            editor: count
            for editor, count in Counter(e.editor for e in edit_count).items()
        },
    }