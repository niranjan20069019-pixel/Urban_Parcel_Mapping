from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.models import (
    Parcel,
    ParcelStatus,
    Project,
    SurveyorEdit,
)
from app.db.repositories import ParcelRepository
from app.gis.geometry import compute_area_km2, compute_perimeter_km

logger = get_logger(__name__)


async def _compute_attrs(geom_wkt: str, crs: str = "EPSG:4326") -> tuple[float, float, str]:
    from shapely.geometry import shape, mapping
    from shapely import wkt

    geom = wkt.loads(geom_wkt.replace("SRID=4326;", ""))
    area = compute_area_km2(geom, crs)
    perimeter = compute_perimeter_km(geom, crs)
    centroid = geom.centroid
    centroid_wkt = f"SRID=4326;{centroid.wkt}"
    return area, perimeter, centroid_wkt


async def create_parcel(
    db: AsyncSession,
    project_id: int,
    geom,
    status: str = "AI_GENERATED",
    **kwargs,
) -> Parcel:
    project = await db.get(Project, project_id)
    if project is None:
        raise AppError(f"Project #{project_id} not found.")

    if isinstance(geom, str):
        geom_wkt = geom
    else:
        geom_wkt = f"SRID=4326;{geom.wkt}"

    area, perimeter, centroid_wkt = await _compute_attrs(geom_wkt)

    parcel = Parcel(
        project_id=project_id,
        geom=geom_wkt,
        version=1,
        status=ParcelStatus(status),
        area=area,
        perimeter=perimeter,
        centroid=centroid_wkt,
        **kwargs,
    )
    db.add(parcel)
    await db.flush()
    await db.refresh(parcel)
    logger.info("Created parcel %d in project %d", parcel.id, project_id)
    return parcel


async def get_parcel(db: AsyncSession, parcel_id: int) -> Parcel:
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None:
        raise AppError(f"Parcel #{parcel_id} not found.")
    return parcel


async def list_parcels(
    db: AsyncSession,
    project_id: int,
    status: str | None = None,
) -> list[Parcel]:
    stmt = select(Parcel).where(Parcel.project_id == project_id)
    if status:
        stmt = stmt.where(Parcel.status == ParcelStatus(status))
    stmt = stmt.order_by(Parcel.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_parcel_geometry(
    db: AsyncSession,
    parcel_id: int,
    new_geom,
    editor: str | None = None,
) -> Parcel:
    parcel = await get_parcel(db, parcel_id)

    if isinstance(new_geom, str):
        new_geom_wkt = new_geom
    else:
        new_geom_wkt = f"SRID=4326;{new_geom.wkt}"

    edit = SurveyorEdit(
        parcel_id=parcel_id,
        editor=editor or "system",
        old_geom=parcel.geom,
        new_geom=new_geom_wkt,
    )
    db.add(edit)

    area, perimeter, centroid_wkt = await _compute_attrs(new_geom_wkt)
    parcel.geom = new_geom_wkt
    parcel.area = area
    parcel.perimeter = perimeter
    parcel.centroid = centroid_wkt
    parcel.version += 1
    parcel.status = ParcelStatus.SURVEYOR_EDITED

    await db.flush()
    await db.refresh(parcel)
    logger.info("Updated parcel %d geometry (version %d) by %s", parcel.id, parcel.version, editor)
    return parcel


async def get_parcel_versions(db: AsyncSession, parcel_id: int) -> list[Parcel]:
    parcel = await get_parcel(db, parcel_id)
    stmt = (
        select(Parcel)
        .where(Parcel.project_id == parcel.project_id)
        .where(
            (Parcel.id == parcel_id)
            | (Parcel.parent_parcel_id == parcel_id)
        )
        .order_by(Parcel.version)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_parcel_history(db: AsyncSession, parcel_id: int) -> dict:
    parcel = await get_parcel(db, parcel_id)
    versions = await get_parcel_versions(db, parcel_id)

    stmt = (
        select(SurveyorEdit)
        .where(SurveyorEdit.parcel_id == parcel_id)
        .order_by(SurveyorEdit.created_at)
    )
    result = await db.execute(stmt)
    edits = list(result.scalars().all())

    return {
        "parcel_id": parcel_id,
        "current_version": parcel.version,
        "versions": [
            {"id": v.id, "version": v.version, "status": v.status.value if isinstance(v.status, ParcelStatus) else v.status}
            for v in versions
        ],
        "edits": [
            {
                "id": e.id,
                "editor": e.editor,
                "notes": e.notes,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in edits
        ],
    }


async def delete_parcel(db: AsyncSession, parcel_id: int) -> bool:
    parcel = await db.get(Parcel, parcel_id)
    if parcel is None:
        return False
    await db.delete(parcel)
    await db.flush()
    logger.info("Deleted parcel %d", parcel_id)
    return True
