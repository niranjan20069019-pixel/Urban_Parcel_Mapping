from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Parcel, ParcelStatus, Project, TopologyIssue
from app.gis.topology import (
    check_duplicates,
    check_gaps,
    check_overlaps,
    check_self_intersections,
    repair_topology,
    validate_parcel_topology,
)
from app.gis.vector import load_vector

logger = get_logger(__name__)


async def _load_parcels_gdf(db: AsyncSession, project_id: int):
    import geopandas as gpd
    from shapely import wkt

    result = await db.execute(
        select(Parcel).where(Parcel.project_id == project_id)
    )
    parcels = list(result.scalars().all())
    if not parcels:
        return gpd.GeoDataFrame(columns=["id", "geometry"], crs="EPSG:4326")

    records = []
    for p in parcels:
        geom_wkt = p.geom
        if geom_wkt and geom_wkt.startswith("SRID=4326;"):
            geom_wkt = geom_wkt.replace("SRID=4326;", "")
        geom = wkt.loads(geom_wkt) if geom_wkt else None
        records.append({"id": p.id, "geometry": geom, "status": p.status.value if isinstance(p.status, ParcelStatus) else p.status})

    return gpd.GeoDataFrame(records, crs="EPSG:4326")


async def _store_issues(db: AsyncSession, project_id: int, issues: list[dict]) -> list[TopologyIssue]:
    stored = []
    for issue in issues:
        ti = TopologyIssue(
            project_id=project_id,
            parcel_id=issue.get("parcel_id"),
            issue_type=issue["issue_type"],
            description=issue.get("description"),
            severity=issue.get("severity", "MEDIUM"),
        )
        db.add(ti)
        stored.append(ti)
    await db.flush()
    return stored


async def validate_parcels(db: AsyncSession, project_id: int) -> dict:
    gdf = await _load_parcels_gdf(db, project_id)
    if gdf.empty:
        return {"total_parcels": 0, "issues": []}

    topology = validate_parcel_topology(gdf)
    issues = []

    for idx1, idx2, area in topology.get("overlaps", []):
        parcel_ids = [int(gdf.iloc[i]["id"]) for i in [idx1, idx2] if i < len(gdf)]
        issues.append({
            "issue_type": "OVERLAP",
            "parcel_id": parcel_ids[0] if parcel_ids else None,
            "description": f"Overlapping parcels {parcel_ids} (area={area:.6f})",
            "severity": "HIGH",
        })

    for gap in topology.get("gaps", []):
        issues.append({
            "issue_type": "GAP",
            "description": f"Gap detected between parcels (area={gap.area:.8f})",
            "severity": "MEDIUM",
        })

    for idx, geom in topology.get("self_intersections", []):
        pid = int(gdf.iloc[idx]["id"]) if idx < len(gdf) else None
        issues.append({
            "issue_type": "SELF_INTERSECTION",
            "parcel_id": pid,
            "description": f"Self-intersecting parcel #{pid}",
            "severity": "HIGH",
        })

    for idx1, idx2 in topology.get("duplicates", []):
        parcel_ids = [int(gdf.iloc[i]["id"]) for i in [idx1, idx2] if i < len(gdf)]
        issues.append({
            "issue_type": "DUPLICATE",
            "parcel_id": parcel_ids[0] if parcel_ids else None,
            "description": f"Duplicate parcels {parcel_ids}",
            "severity": "MEDIUM",
        })

    await _store_issues(db, project_id, issues)
    logger.info("Validated %d parcels in project %d, found %d issues", len(gdf), project_id, len(issues))
    return {"total_parcels": len(gdf), "issues": issues}


async def auto_repair_parcels(db: AsyncSession, project_id: int) -> dict:
    gdf = await _load_parcels_gdf(db, project_id)
    if gdf.empty:
        return {"repairs": []}

    repaired_gdf, changes = repair_topology(gdf)
    repairs = []

    for change in changes:
        pid = None
        idx = change["idx"]
        if idx < len(gdf):
            pid = int(gdf.iloc[idx]["id"])

        if change["issue"] == "empty":
            parcel = await db.get(Parcel, pid)
            if parcel:
                await db.delete(parcel)

        repairs.append({"parcel_id": pid, "issue": change["issue"], "detail": change["detail"]})

    await db.flush()
    logger.info("Repaired %d issues in project %d", len(repairs), project_id)
    return {"repairs": repairs}


async def get_topology_issues(
    db: AsyncSession,
    project_id: int,
    severity: str | None = None,
) -> list[TopologyIssue]:
    stmt = select(TopologyIssue).where(
        TopologyIssue.project_id == project_id,
        TopologyIssue.resolved == False,
    )
    if severity:
        stmt = stmt.where(TopologyIssue.severity == severity)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def resolve_issue(db: AsyncSession, issue_id: int) -> bool:
    issue = await db.get(TopologyIssue, issue_id)
    if issue is None:
        return False
    issue.resolved = True
    await db.flush()
    logger.info("Resolved topology issue %d", issue_id)
    return True
