from __future__ import annotations

import geopandas as gpd
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

CHANGE_TYPES = {
    "UNCHANGED": "UNCHANGED",
    "BOUNDARY_SHIFT": "BOUNDARY_SHIFT",
    "SUBDIVISION": "SUBDIVISION",
    "MERGER": "MERGER",
    "NEW": "NEW",
    "REMOVED": "REMOVED",
    "CONFLICT": "CONFLICT",
    "UNCERTAIN": "UNCERTAIN",
}

_IOU_THRESHOLDS = {
    "high": 0.8,
    "medium": 0.4,
    "low": 0.1,
}

_SHIFT_THRESHOLD = 0.0005  # ~50m in degrees


def classify_changes(comparison_results: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if comparison_results.empty:
        return gpd.GeoDataFrame(columns=["geometry", "change_type", "confidence", "evidence"])

    records = []
    for _, row in comparison_results.iterrows():
        iou = row.get("iou", 0.0)
        bd = row.get("boundary_displacement", float("inf"))
        ad = row.get("area_difference", 0.0)
        cd = row.get("centroid_distance", float("inf"))
        old_idx = row.get("old_index", -1)
        new_idx = row.get("new_index", -1)

        evidence = {
            "iou": iou,
            "boundary_displacement": bd,
            "area_difference": ad,
            "centroid_distance": cd,
        }

        if old_idx >= 0 and new_idx >= 0:
            if iou >= _IOU_THRESHOLDS["high"] and bd < _SHIFT_THRESHOLD:
                change_type = "UNCHANGED"
                confidence = 0.95
            elif iou >= _IOU_THRESHOLDS["medium"] and bd >= _SHIFT_THRESHOLD:
                change_type = "BOUNDARY_SHIFT"
                confidence = 0.8
            elif iou >= _IOU_THRESHOLDS["low"] and bd < _SHIFT_THRESHOLD:
                change_type = "BOUNDARY_SHIFT"
                confidence = 0.6
            else:
                change_type = "CONFLICT"
                confidence = 0.5
        elif old_idx >= 0 and new_idx == -1:
            change_type = "REMOVED"
            confidence = 0.9
        elif old_idx == -1 and new_idx >= 0:
            change_type = "NEW"
            confidence = 0.85
        else:
            change_type = "UNCERTAIN"
            confidence = 0.3

        records.append({
            "geometry": row.geometry,
            "change_type": change_type,
            "confidence": confidence,
            "evidence": evidence,
            "old_index": old_idx,
            "new_index": new_idx,
        })

    gdf = gpd.GeoDataFrame(records, crs=comparison_results.crs)

    old_counts = {}
    new_counts = {}
    for _, row in gdf.iterrows():
        oi = row.get("old_index", -1)
        ni = row.get("new_index", -1)
        if oi >= 0:
            old_counts[oi] = old_counts.get(oi, 0) + 1
        if ni >= 0:
            new_counts[ni] = new_counts.get(ni, 0) + 1

    for idx in gdf.index:
        row = gdf.loc[idx]
        oi = row.get("old_index", -1)
        ni = row.get("new_index", -1)
        if oi >= 0 and old_counts.get(oi, 0) > 1:
            gdf.at[idx, "change_type"] = "SUBDIVISION"
            gdf.at[idx, "confidence"] = 0.75
        elif ni >= 0 and new_counts.get(ni, 0) > 1:
            gdf.at[idx, "change_type"] = "MERGER"
            gdf.at[idx, "confidence"] = 0.75

    logger.info("Classified %d changes: %s",
                len(gdf),
                {ct: int((gdf["change_type"] == ct).sum()) for ct in gdf["change_type"].unique()})
    return gdf
