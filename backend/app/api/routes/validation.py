from __future__ import annotations

import geopandas as gpd
from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping as shapely_mapping
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import Parcel, ParcelStatus, Project, TopologyIssue
from app.gis.topology import repair_topology, validate_parcel_topology
from app.schemas.validation import TopologyIssueResponse

logger = get_logger(__name__)

router = APIRouter(tags=["validation"])


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project #{project_id} not found")
    return proj


def _parcels_gdf(db_parcels: list[Parcel]) -> gpd.GeoDataFrame:
    geoms = [to_shape(p.geom) for p in db_parcels]
    return gpd.GeoDataFrame(
        {"db_id": [p.id for p in db_parcels],
         "status": [p.status.name for p in db_parcels]},
        geometry=geoms,
        crs="EPSG:4326",
    )


@router.post("/projects/{project_id}/validate/topology")
async def validate_topology(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    await _get_project_or_404(project_id, db)
    parcels = (await db.execute(select(Parcel).where(Parcel.project_id == project_id))).scalars().all()
    if not parcels:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No parcels found for project #{project_id}")

    report = validate_parcel_topology(_parcels_gdf(parcels))

    existing = (await db.execute(
        select(TopologyIssue).where(TopologyIssue.project_id == project_id)
    )).scalars().all()
    for row in existing:
        await db.delete(row)

    for parcel_a, parcel_b, area in report["overlaps"]:
        db.add(TopologyIssue(
            project_id=project_id,
            issue_type="overlap",
            description=f"Overlap of {area:.2f} units between parcels #{parcel_a} and #{parcel_b}",
            severity="HIGH",
        ))
    for idx, _geom in report["self_intersections"]:
        db.add(TopologyIssue(
            project_id=project_id,
            issue_type="self_intersection",
            description=f"Parcel #{idx} has an invalid/self-intersecting geometry",
            severity="HIGH",
        ))
    for parcel_a, parcel_b in report["duplicates"]:
        db.add(TopologyIssue(
            project_id=project_id,
            issue_type="duplicate",
            description=f"Parcels #{parcel_a} and #{parcel_b} are geometrically identical",
            severity="MEDIUM",
        ))

    await db.flush()

    return {
        "project_id": project_id,
        "total_parcels": report["total_parcels"],
        "valid_geometry_count": report["valid_geometry_count"],
        "issues_found": report["issues_found"],
        "overlap_count": len(report["overlaps"]),
        "gap_count": len(report["gaps"]),
        "self_intersection_count": len(report["self_intersections"]),
        "duplicate_count": len(report["duplicates"]),
    }


@router.post("/projects/{project_id}/validate/repair")
async def repair_topology_issues(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    await _get_project_or_404(project_id, db)
    parcels = (await db.execute(select(Parcel).where(Parcel.project_id == project_id))).scalars().all()
    if not parcels:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No parcels found for project #{project_id}")

    gdf = _parcels_gdf(parcels)
    repaired, changes = repair_topology(gdf)
    fixed = 0
    for idx, row in repaired.iterrows():
        geom = row.geometry
        db_id = int(row["db_id"])
        if geom.is_empty or geom.area <= 0:
            await db.delete(await db.get(Parcel, db_id))
            fixed += 1
            continue
        parcel = await db.get(Parcel, db_id)
        if parcel is None:
            continue
        if any(c["idx"] == idx for c in changes):
            fixed += 1
        parcel.geom = WKTElement(geom.wkt, srid=4326)
        parcel.area = geom.area
        parcel.perimeter = geom.length
        if parcel.status == ParcelStatus.AI_GENERATED:
            parcel.status = ParcelStatus.SURVEYOR_EDITED

    issues = (await db.execute(
        select(TopologyIssue).where(TopologyIssue.project_id == project_id, TopologyIssue.resolved.is_(False))
    )).scalars().all()
    for issue in issues:
        issue.resolved = True

    await db.flush()
    return {"project_id": project_id, "repaired": fixed, "changes": changes, "issues_resolved": len(issues)}


@router.get("/projects/{project_id}/topology-issues", response_model=list[TopologyIssueResponse])
async def list_topology_issues(
    project_id: int,
    resolved: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[TopologyIssueResponse]:
    await _get_project_or_404(project_id, db)
    stmt = select(TopologyIssue).where(TopologyIssue.project_id == project_id)
    if resolved is not None:
        stmt = stmt.where(TopologyIssue.resolved.is_(resolved))
    stmt = stmt.order_by(TopologyIssue.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [
        TopologyIssueResponse(
            id=i.id,
            issue_type=i.issue_type,
            description=i.description or "",
            severity=i.severity or "UNKNOWN",
            resolved=i.resolved,
            geom_json=shapely_mapping(to_shape(i.geom)) if i.geom is not None else None,
        )
        for i in rows
    ]