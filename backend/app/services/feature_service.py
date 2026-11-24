from __future__ import annotations

import numpy as np
import rasterio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Building, BoundaryEvidence, LanduseFeature, Prediction, Road
from app.gis.geometry import mask_to_polygons, repair_geometry, simplify_geometry
from app.gis.vector import load_vector, save_vector

logger = get_logger(__name__)

_CLASS_IDS = {
    "buildings": 1,
    "roads": 2,
    "landuse": 3,
    "boundary": 4,
}


async def _load_prediction_mask(prediction_id: int, db: AsyncSession) -> tuple[np.ndarray, rasterio.Affine, str | None]:
    pred = await db.get(Prediction, prediction_id)
    if pred is None:
        raise ValueError(f"Prediction #{prediction_id} not found.")

    mask_dir = pred.file_path
    from pathlib import Path
    masks = sorted(Path(mask_dir).glob("*_mask.npy"))
    if not masks:
        raise ValueError(f"No masks in {mask_dir}")

    mask = np.load(str(masks[0]))

    from app.db.models import Raster
    raster = await db.get(Raster, pred.raster_id)

    with rasterio.open(raster.file_path) as src:
        transform = src.transform
        crs = str(src.crs) if src.crs else None

    return mask, transform, crs


async def extract_buildings(db: AsyncSession, project_id: int, prediction_id: int) -> list[Building]:
    mask, transform, crs = await _load_prediction_mask(prediction_id, db)
    binary = (mask == _CLASS_IDS["buildings"]).astype(np.uint8)

    polys_conf = mask_to_polygons(binary, transform, min_area=5.0, simplify_tolerance=2.0)
    buildings = []
    for geom, conf in polys_conf:
        geom = repair_geometry(geom)
        if geom.is_empty:
            continue
        building = Building(
            prediction_id=prediction_id,
            project_id=project_id,
            geom=f"SRID=4326;{geom.wkt}",
            area=geom.area,
            perimeter=geom.length,
            centroid=f"SRID=4326;{geom.centroid.wkt}",
            confidence=conf,
        )
        db.add(building)
        buildings.append(building)

    await db.flush()
    logger.info("Extracted %d buildings from prediction %d", len(buildings), prediction_id)
    return buildings


async def extract_roads(db: AsyncSession, project_id: int, prediction_id: int) -> list[Road]:
    mask, transform, crs = await _load_prediction_mask(prediction_id, db)
    binary = (mask == _CLASS_IDS["roads"]).astype(np.uint8)

    polys_conf = mask_to_polygons(binary, transform, min_area=3.0, simplify_tolerance=1.0)
    roads = []
    for geom, conf in polys_conf:
        geom = repair_geometry(geom)
        if geom.is_empty:
            continue
        road = Road(
            prediction_id=prediction_id,
            project_id=project_id,
            geom=f"SRID=4326;{geom.wkt}",
            length=geom.length,
            confidence=conf,
        )
        db.add(road)
        roads.append(road)

    await db.flush()
    logger.info("Extracted %d roads from prediction %d", len(roads), prediction_id)
    return roads


async def extract_landuse(db: AsyncSession, project_id: int, prediction_id: int) -> list[LanduseFeature]:
    mask, transform, crs = await _load_prediction_mask(prediction_id, db)

    landuse_classes = np.unique(mask[mask > 0])
    features = []
    for cls_id in landuse_classes:
        if cls_id == 0 or cls_id in _CLASS_IDS.values():
            continue
        binary = (mask == cls_id).astype(np.uint8)
        polys_conf = mask_to_polygons(binary, transform, min_area=10.0, simplify_tolerance=3.0)
        for geom, conf in polys_conf:
            geom = repair_geometry(geom)
            if geom.is_empty:
                continue
            feat = LanduseFeature(
                prediction_id=prediction_id,
                project_id=project_id,
                geom=f"SRID=4326;{geom.wkt}",
                landuse_class=str(cls_id),
                area=geom.area,
                confidence=conf,
            )
            db.add(feat)
            features.append(feat)

    await db.flush()
    logger.info("Extracted %d landuse features from prediction %d", len(features), prediction_id)
    return features


async def extract_boundary_evidence(db: AsyncSession, project_id: int, prediction_id: int) -> list[BoundaryEvidence]:
    mask, transform, crs = await _load_prediction_mask(prediction_id, db)
    binary = (mask == _CLASS_IDS["boundary"]).astype(np.uint8)

    from app.gis.geometry import extract_contours
    lines = extract_contours(binary, transform)

    features = []
    for line in lines:
        if line.is_empty:
            continue
        feat = BoundaryEvidence(
            prediction_id=prediction_id,
            project_id=project_id,
            geom=f"SRID=4326;{line.wkt}",
            boundary_type="ai_detected",
            confidence=0.7,
        )
        db.add(feat)
        features.append(feat)

    await db.flush()
    logger.info("Extracted %d boundary evidences from prediction %d", len(features), prediction_id)
    return features
