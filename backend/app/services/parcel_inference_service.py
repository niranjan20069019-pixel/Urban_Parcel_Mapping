from __future__ import annotations

from typing import Any

import geopandas as gpd
import numpy as np
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from app.core.logging import get_logger
from app.gis.geometry import compute_area_km2, repair_geometry, simplify_geometry
from app.gis.topology import repair_topology

logger = get_logger(__name__)

_CONFIDENCE_WEIGHTS = {
    "has_existing_parcels": 0.20,
    "road_separation": 0.15,
    "building_density": 0.15,
    "boundary_evidence": 0.15,
    "gnss_support": 0.15,
    "landuse_consistency": 0.10,
    "area_plausibility": 0.10,
}


def _compute_area_km2(geom, crs="EPSG:4326") -> float:
    try:
        return compute_area_km2(geom, crs)
    except Exception:
        return geom.area


def _split_by_roads(region: Polygon, roads_gdf: gpd.GeoDataFrame) -> list[Polygon]:
    if roads_gdf is None or roads_gdf.empty:
        return [region]

    road_union = unary_union(roads_gdf.geometry.tolist())
    if not region.intersects(road_union):
        return [region]

    from shapely.ops import split
    parts = split(region, road_union)
    return [p for p in parts.geoms if isinstance(p, Polygon) and p.area > 0]


def _estimate_subdivisions(region: Polygon, buildings_gdf: gpd.GeoDataFrame | None) -> int:
    if buildings_gdf is None or buildings_gdf.empty:
        return 1

    region_box = region
    buildings_in = buildings_gdf[buildings_gdf.intersects(region_box)]
    if buildings_in.empty:
        return 1

    n_buildings = len(buildings_in)
    if n_buildings <= 2:
        return 1
    if n_buildings <= 5:
        return 2
    return max(2, n_buildings // 3)


def _compute_confidence(
    has_existing: bool,
    roads_split: bool,
    n_buildings: int,
    n_boundaries: int,
    gnss_inside: bool,
    landuse_match: bool,
    area_km2: float,
) -> float:
    scores = {
        "has_existing_parcels": 1.0 if has_existing else 0.3,
        "road_separation": 0.9 if roads_split else 0.4,
        "building_density": min(1.0, n_buildings / 5.0),
        "boundary_evidence": min(1.0, n_boundaries / 3.0),
        "gnss_support": 1.0 if gnss_inside else 0.2,
        "landuse_consistency": 0.8 if landuse_match else 0.4,
        "area_plausibility": min(1.0, area_km2 / 0.01) if area_km2 > 0 else 0.3,
    }
    return sum(scores[k] * _CONFIDENCE_WEIGHTS[k] for k in scores)


def infer_parcels(
    project_id: int,
    inputs: dict[str, Any],
) -> gpd.GeoDataFrame:
    buildings_gdf = inputs.get("buildings_gdf")
    roads_gdf = inputs.get("roads_gdf")
    landuse_gdf = inputs.get("landuse_gdf")
    boundary_gdf = inputs.get("boundary_gdf")
    existing_parcels_gdf = inputs.get("existing_parcels_gdf")
    gnss_gdf = inputs.get("gnss_gdf")

    candidate_records: list[dict] = []

    study_area = None
    if existing_parcels_gdf is not None and not existing_parcels_gdf.empty:
        study_area = unary_union(existing_parcels_gdf.geometry.tolist())
    elif buildings_gdf is not None and not buildings_gdf.empty:
        study_area = buildings_gdf.geometry.unary_union.buffer(0.001)

    if study_area is None:
        logger.warning("No study area derived from inputs for project %d", project_id)
        return gpd.GeoDataFrame(columns=["geometry", "confidence", "reasoning"], crs="EPSG:4326")

    if isinstance(study_area, MultiPolygon):
        regions = list(study_area.geoms)
    elif isinstance(study_area, Polygon):
        regions = [study_area]
    else:
        regions = []

    for region in regions:
        region = repair_geometry(region)
        if region.is_empty:
            continue

        sub_regions = _split_by_roads(region, roads_gdf) if roads_gdf is not None and not roads_gdf.empty else [region]

        n_buildings = 0
        if buildings_gdf is not None and not buildings_gdf.empty:
            n_buildings = len(buildings_gdf[buildings_gdf.intersects(region)])

        n_boundaries = 0
        if boundary_gdf is not None and not boundary_gdf.empty:
            n_boundaries = len(boundary_gdf[boundary_gdf.intersects(region)])

        gnss_inside = False
        if gnss_gdf is not None and not gnss_gdf.empty:
            gnss_inside = bool(gnss_gdf[gnss_gdf.within(region)].shape[0] > 0)

        landuse_match = False
        if landuse_gdf is not None and not landuse_gdf.empty:
            landuse_match = bool(landuse_gdf[landuse_gdf.intersects(region)].shape[0] > 0)

        has_existing = existing_parcels_gdf is not None and not existing_parcels_gdf.empty

        for sub in sub_regions:
            sub = repair_geometry(sub)
            if sub.is_empty or sub.area < 1e-8:
                continue

            confidence = _compute_confidence(
                has_existing=has_existing,
                roads_split=len(sub_regions) > 1,
                n_buildings=n_buildings,
                n_boundaries=n_boundaries,
                gnss_inside=gnss_inside,
                landuse_match=landuse_match,
                area_km2=_compute_area_km2(sub),
            )

            reasoning = {
                "source": "existing_parcel_subdivision" if has_existing else "new_candidate",
                "has_existing_parcels": has_existing,
                "roads_split": len(sub_regions) > 1,
                "building_count_nearby": n_buildings,
                "boundary_evidence_count": n_boundaries,
                "gnss_inside": gnss_inside,
                "landuse_match": landuse_match,
            }

            candidate_records.append({
                "geometry": sub,
                "confidence": confidence,
                "reasoning": reasoning,
            })

    if not candidate_records:
        logger.warning("No candidate parcels generated for project %d", project_id)
        return gpd.GeoDataFrame(columns=["geometry", "confidence", "reasoning"], crs="EPSG:4326")

    gdf = gpd.GeoDataFrame(candidate_records, crs="EPSG:4326")
    gdf["project_id"] = project_id
    logger.info("Inferred %d candidate parcels for project %d", len(gdf), project_id)
    return gdf
