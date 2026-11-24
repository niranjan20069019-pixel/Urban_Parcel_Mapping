from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping as shapely_mapping
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import (
    BoundaryEvidence,
    Building,
    LanduseFeature,
    Project,
    Road,
)
from app.schemas.features import (
    BoundaryResponse,
    BuildingResponse,
    FeatureCollectionResponse,
    LanduseResponse,
    RoadResponse,
)

logger = get_logger(__name__)

router = APIRouter(tags=["features"])

FEATURE_MODELS = {
    "buildings": (Building, BuildingResponse),
    "roads": (Road, RoadResponse),
    "landuse": (LanduseFeature, LanduseResponse),
    "boundaries": (BoundaryEvidence, BoundaryResponse),
}


def _geom_json(geom) -> dict | None:
    if geom is None:
        return None
    return shapely_mapping(to_shape(geom))


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project #{project_id} not found")
    return proj


@router.get("/projects/{project_id}/buildings", response_model=list[BuildingResponse])
async def list_buildings(project_id: int, db: AsyncSession = Depends(get_db)) -> list[BuildingResponse]:
    await _get_project_or_404(project_id, db)
    rows = (await db.execute(select(Building).where(Building.project_id == project_id).order_by(Building.id))).scalars().all()
    return [
        BuildingResponse(
            id=b.id,
            area=b.area or 0.0,
            perimeter=b.perimeter or 0.0,
            confidence=b.confidence or 0.0,
            height=b.height,
            geom_json=_geom_json(b.geom) or {},
        )
        for b in rows
    ]


@router.get("/projects/{project_id}/roads", response_model=list[RoadResponse])
async def list_roads(project_id: int, db: AsyncSession = Depends(get_db)) -> list[RoadResponse]:
    await _get_project_or_404(project_id, db)
    rows = (await db.execute(select(Road).where(Road.project_id == project_id).order_by(Road.id))).scalars().all()
    return [
        RoadResponse(
            id=r.id,
            road_class=r.road_class or "unknown",
            width=r.width,
            length=r.length or 0.0,
            confidence=r.confidence or 0.0,
            geom_json=_geom_json(r.geom) or {},
            centerline_json=_geom_json(r.centerline),
        )
        for r in rows
    ]


@router.get("/projects/{project_id}/landuse", response_model=list[LanduseResponse])
async def list_landuse(project_id: int, db: AsyncSession = Depends(get_db)) -> list[LanduseResponse]:
    await _get_project_or_404(project_id, db)
    rows = (await db.execute(select(LanduseFeature).where(LanduseFeature.project_id == project_id).order_by(LanduseFeature.id))).scalars().all()
    return [
        LanduseResponse(
            id=l.id,
            landuse_class=l.landuse_class,
            area=l.area or 0.0,
            confidence=l.confidence or 0.0,
            geom_json=_geom_json(l.geom) or {},
        )
        for l in rows
    ]


@router.get("/projects/{project_id}/boundaries", response_model=list[BoundaryResponse])
async def list_boundaries(project_id: int, db: AsyncSession = Depends(get_db)) -> list[BoundaryResponse]:
    await _get_project_or_404(project_id, db)
    rows = (await db.execute(select(BoundaryEvidence).where(BoundaryEvidence.project_id == project_id).order_by(BoundaryEvidence.id))).scalars().all()
    return [
        BoundaryResponse(
            id=b.id,
            boundary_type=b.boundary_type or "unknown",
            confidence=b.confidence or 0.0,
            geom_json=_geom_json(b.geom) or {},
        )
        for b in rows
    ]


@router.get("/projects/{project_id}/features/{feature_type}/geojson", response_model=FeatureCollectionResponse)
async def get_features_geojson(
    project_id: int,
    feature_type: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureCollectionResponse:
    await _get_project_or_404(project_id, db)
    mapping = FEATURE_MODELS.get(feature_type)
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown feature type '{feature_type}'. Supported: {sorted(FEATURE_MODELS)}",
        )
    model, _ = mapping
    rows = (await db.execute(select(model).where(model.project_id == project_id))).scalars().all()

    features = []
    for row in rows:
        geom = to_shape(row.geom)
        props = {}
        for col in row.__table__.columns:
            if col.name in ("geom", "prediction_id", "id", "created_at", "updated_at"):
                continue
            if col.type.__class__.__name__ == "Geometry":
                continue
            value = getattr(row, col.name)
            if hasattr(value, "value"):
                value = value.value
            props[col.name] = value
        features.append(
            {"type": "Feature", "properties": props, "geometry": shapely_mapping(geom)}
        )
    return FeatureCollectionResponse(features=features)