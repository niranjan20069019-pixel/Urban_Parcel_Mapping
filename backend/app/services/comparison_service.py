from __future__ import annotations

import geopandas as gpd
import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from app.core.logging import get_logger
from app.gis.distance import (
    area_difference,
    boundary_displacement,
    centroid_distance,
    hausdorff_distance,
    polygon_iou,
)

logger = get_logger(__name__)


def _match_parcels(
    old_gdf: gpd.GeoDataFrame,
    new_gdf: gpd.GeoDataFrame,
) -> list[tuple[int, int, float]]:
    pairs = []
    old_geoms = list(old_gdf.geometry)
    new_geoms = list(new_gdf.geometry)

    for j, new_geom in enumerate(new_geoms):
        if new_geom is None or new_geom.is_empty:
            continue
        best_i, best_score = -1, 0.0
        for i, old_geom in enumerate(old_geoms):
            if old_geom is None or old_geom.is_empty:
                continue
            try:
                score = polygon_iou(old_geom, new_geom)
            except Exception:
                score = 0.0
            if score > best_score:
                best_score = score
                best_i = i
        if best_i >= 0:
            pairs.append((best_i, j, best_score))

    return pairs


def compare_parcel_sets(
    old_parcels_gdf: gpd.GeoDataFrame,
    new_parcels_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    if old_parcels_gdf.empty and new_parcels_gdf.empty:
        return gpd.GeoDataFrame(columns=["geometry", "iou", "area_difference", "centroid_distance", "boundary_displacement", "hausdorff_distance"])

    if old_parcels_gdf.empty:
        records = []
        for _, row in new_parcels_gdf.iterrows():
            records.append({
                "geometry": row.geometry,
                "iou": 0.0,
                "area_difference": row.geometry.area if row.geometry else 0,
                "centroid_distance": float("inf"),
                "boundary_displacement": float("inf"),
                "hausdorff_distance": float("inf"),
            })
        return gpd.GeoDataFrame(records, crs=new_parcels_gdf.crs)

    if new_parcels_gdf.empty:
        records = []
        for _, row in old_parcels_gdf.iterrows():
            records.append({
                "geometry": row.geometry,
                "iou": 0.0,
                "area_difference": -(row.geometry.area if row.geometry else 0),
                "centroid_distance": float("inf"),
                "boundary_displacement": float("inf"),
                "hausdorff_distance": float("inf"),
            })
        return gpd.GeoDataFrame(records, crs=old_parcels_gdf.crs)

    matches = _match_parcels(old_parcels_gdf, new_parcels_gdf)

    matched_old = {m[0] for m in matches}
    matched_new = {m[1] for m in matches}

    records = []
    old_geoms = list(old_parcels_gdf.geometry)
    new_geoms = list(new_parcels_gdf.geometry)

    for old_i, new_j, iou_score in matches:
        geom_old = old_geoms[old_i]
        geom_new = new_geoms[new_j]

        try:
            iou_val = polygon_iou(geom_old, geom_new)
            bd = boundary_displacement(geom_old, geom_new)
            cd = centroid_distance(geom_old, geom_new)
            hd = hausdorff_distance(geom_old, geom_new)
            ad = area_difference(geom_old, geom_new)
        except Exception:
            iou_val, bd, cd, hd, ad = iou_score, 0.0, 0.0, 0.0, 0.0

        records.append({
            "geometry": geom_new,
            "old_index": old_i,
            "new_index": new_j,
            "iou": iou_val,
            "area_difference": ad,
            "centroid_distance": cd,
            "boundary_displacement": bd,
            "hausdorff_distance": hd,
        })

    for j, geom in enumerate(new_geoms):
        if j not in matched_new:
            records.append({
                "geometry": geom,
                "old_index": -1,
                "new_index": j,
                "iou": 0.0,
                "area_difference": geom.area if geom else 0,
                "centroid_distance": float("inf"),
                "boundary_displacement": float("inf"),
                "hausdorff_distance": float("inf"),
            })

    for i, geom in enumerate(old_geoms):
        if i not in matched_old:
            records.append({
                "geometry": geom,
                "old_index": i,
                "new_index": -1,
                "iou": 0.0,
                "area_difference": -(geom.area if geom else 0),
                "centroid_distance": float("inf"),
                "boundary_displacement": float("inf"),
                "hausdorff_distance": float("inf"),
            })

    if not records:
        return gpd.GeoDataFrame(columns=["geometry", "iou", "area_difference", "centroid_distance", "boundary_displacement", "hausdorff_distance"])

    result = gpd.GeoDataFrame(records, crs=old_parcels_gdf.crs or new_parcels_gdf.crs)
    logger.info("Compared %d old vs %d new parcels -> %d records", len(old_parcels_gdf), len(new_parcels_gdf), len(result))
    return result
