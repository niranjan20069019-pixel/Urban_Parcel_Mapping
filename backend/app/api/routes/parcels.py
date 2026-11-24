from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping as shapely_mapping, shape as shapely_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import Parcel, ParcelStatus, Project, Recommendation, SurveyorEdit, Validation
from app.schemas.parcels import ParcelEditRequest, ParcelResponse

logger = get_logger(__name__)

router = APIRouter(tags=["parcels"])

VALID_STATUSES = {s.name for s in ParcelStatus}


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project #{project_id} not found")
    return proj


async def _get_parcel_or_404(parcel_id: int, db: AsyncSession) -> Parcel:
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parcel #{parcel_id} not found")
    return parcel


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


@router.post("/projects/{project_id}/parcels/infer")
async def infer_parcels(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate parcels from boundary evidence predictions.

    Uses the latest boundary prediction mask saved by the inference pipeline,
    polygons are extracted and stored as new AI_GENERATED parcels.
    """
    await _get_project_or_404(project_id, db)
    prediction_dir = settings.DATA_DIR / f"project_{project_id}" / "predictions"
    mask_path = prediction_dir / "segformer_boundary.npy"
    if not mask_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No boundary prediction found. Run inference first, then retry parcel inference.",
        )

    import numpy as np
    from app.gis.geometry import repair_geometry

    mask = np.load(mask_path)
    from rasterio.features import shapes as rio_shapes

    created = 0
    for geom_dict, value in rio_shapes(mask.astype(np.uint8), mask=(mask > 0)):
        if value == 0:
            continue
        geom = shapely_shape(geom_dict)
        if geom.is_empty:
            continue
        geom = repair_geometry(geom)

        centroid = geom.centroid
        parcel = Parcel(
            project_id=project_id,
            geom=WKTElement(geom.wkt, srid=4326),
            version=1,
            status=ParcelStatus.AI_GENERATED,
            area=geom.area,
            perimeter=geom.length,
            centroid=WKTElement(centroid.wkt, srid=4326),
            confidence=float(np.mean(mask[mask > 0])) if (mask > 0).any() else 0.0,
            metadata_json={"source": "segformer_boundary"},
        )
        db.add(parcel)
        created += 1

    await db.flush()
    logger.info("Inferred %d parcels for project %d", created, project_id)
    return {"project_id": project_id, "created": created, "status": "completed"}


@router.get("/projects/{project_id}/parcels", response_model=list[ParcelResponse])
async def list_parcels(
    project_id: int,
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> list[ParcelResponse]:
    await _get_project_or_404(project_id, db)
    stmt = select(Parcel).where(Parcel.project_id == project_id)
    if status_filter:
        normalized = status_filter.upper()
        if normalized not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status '{status_filter}'. Valid: {sorted(VALID_STATUSES)}",
            )
        stmt = stmt.where(Parcel.status == normalized)
    stmt = stmt.order_by(Parcel.id)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(p) for p in rows]


@router.get("/parcels/{parcel_id}", response_model=ParcelResponse)
async def get_parcel(parcel_id: int, db: AsyncSession = Depends(get_db)) -> ParcelResponse:
    parcel = await _get_parcel_or_404(parcel_id, db)
    return _to_response(parcel)


@router.put("/parcels/{parcel_id}/edit", response_model=ParcelResponse)
async def edit_parcel(
    parcel_id: int,
    body: ParcelEditRequest,
    db: AsyncSession = Depends(get_db),
) -> ParcelResponse:
    parcel = await _get_parcel_or_404(parcel_id, db)

    old_geom = to_shape(parcel.geom)
    new_shape = shapely_shape(body.geom_json)
    if not new_shape.is_valid:
        new_shape = new_shape.buffer(0)

    parcel.surveyor_edits.append(
        SurveyorEdit(
            parcel_id=parcel.id,
            editor=body.editor,
            old_geom=WKTElement(old_geom.wkt, srid=4326),
            new_geom=WKTElement(new_shape.wkt, srid=4326),
            notes=body.notes,
        )
    )

    parcel.geom = WKTElement(new_shape.wkt, srid=4326)
    parcel.area = new_shape.area
    parcel.perimeter = new_shape.length
    parcel.centroid = WKTElement(new_shape.centroid.wkt, srid=4326)
    parcel.status = ParcelStatus.SURVEYOR_EDITED
    parcel.confidence = parcel.confidence or 0.5
    await db.flush()
    await db.refresh(parcel)
    logger.info("Parcel %d edited by %s", parcel_id, body.editor)
    return _to_response(parcel)


@router.post("/parcels/{parcel_id}/accept", response_model=ParcelResponse)
async def accept_parcel(
    parcel_id: int,
    validator: str = "system",
    db: AsyncSession = Depends(get_db),
) -> ParcelResponse:
    parcel = await _get_parcel_or_404(parcel_id, db)
    parcel.status = ParcelStatus.FINAL_VALIDATED
    await db.flush()
    await db.refresh(parcel)
    db.add(
        Validation(
            parcel_id=parcel_id,
            validator=validator,
            validation_type="acceptance",
            status="accepted",
            notes="Parcel accepted",
        )
    )
    await db.flush()
    logger.info("Parcel %d accepted by %s", parcel_id, validator)
    return _to_response(parcel)


@router.post("/parcels/{parcel_id}/reject", response_model=ParcelResponse)
async def reject_parcel(
    parcel_id: int,
    reason: str = "",
    validator: str = "system",
    db: AsyncSession = Depends(get_db),
) -> ParcelResponse:
    parcel = await _get_parcel_or_404(parcel_id, db)
    parcel.status = ParcelStatus.AI_GENERATED
    await db.flush()
    db.add(
        Validation(
            parcel_id=parcel_id,
            validator=validator,
            validation_type="acceptance",
            status="rejected",
            notes=reason or "Parcel rejected",
        )
    )
    await db.flush()
    logger.info("Parcel %d rejected by %s", parcel_id, validator)
    return _to_response(parcel)


@router.get("/parcels/{parcel_id}/versions")
async def parcel_versions(parcel_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    parcel = await _get_parcel_or_404(parcel_id, db)
    edits = (await db.execute(select(SurveyorEdit).where(SurveyorEdit.parcel_id == parcel_id).order_by(SurveyorEdit.created_at))).scalars().all()
    versions = [
        {
            "id": e.id,
            "version": v,
            "editor": e.editor,
            "old_geom": shapely_mapping(to_shape(e.old_geom)),
            "new_geom": shapely_mapping(to_shape(e.new_geom)),
            "notes": e.notes,
            "created_at": str(e.created_at),
        }
        for v, e in enumerate(edits, start=1)
    ]
    return {
        "parcel_id": parcel_id,
        "current_version": parcel.version,
        "surveyor_edit_count": len(edits),
        "versions": versions,
    }


@router.get("/parcels/{parcel_id}/confidence")
async def parcel_confidence(parcel_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    parcel = await _get_parcel_or_404(parcel_id, db)
    overall = parcel.confidence or 0.0
    breakdown = {
        "ai_agreement": overall,
        "canopy": None,
        "gnss_agreement": None,
        "topology_validity": None,
        "area_plausibility": None,
        "boundary_evidence": None,
    }
    if parcel.status in ("GNSS_VALIDATED", "FINAL_VALIDATED"):
        breakdown["gnss_agreement"] = round(overall * 0.9, 4)
        breakdown["topology_validity"] = 1.0
    breakdown["weighted_score"] = overall
    return {"parcel_id": parcel_id, "breakdown": breakdown, "overall": overall}


@router.get("/parcels/{parcel_id}/recommendations")
async def parcel_recommendations(parcel_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    await _get_parcel_or_404(parcel_id, db)
    rows = (await db.execute(select(Recommendation).where(Recommendation.parcel_id == parcel_id).order_by(Recommendation.created_at.desc()))).scalars().all()
    return {
        "parcel_id": parcel_id,
        "total": len(rows),
        "recommendations": [
            {
                "id": r.id,
                "action": r.action,
                "priority": r.priority,
                "reason": r.reason,
                "evidence": r.evidence_json,
                "created_at": str(r.created_at),
                "acknowledged_at": str(r.acknowledged_at) if r.acknowledged_at else None,
            }
            for r in rows
        ],
    }