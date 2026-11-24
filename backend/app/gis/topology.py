"""Topology validation and repair for parcel polygon datasets."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import geopandas as gpd
import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from .geometry import repair_geometry, simplify_geometry


def validate_parcel_topology(parcels_gdf: gpd.GeoDataFrame) -> dict:
    """Run all topology checks and return a summary dict.

    Returns::

        {
            "total_parcels": int,
            "overlaps": [...],
            "gaps": [...],
            "self_intersections": [...],
            "duplicates": [...],
            "slivers": [...],
            "valid_geometry_count": int,
            "issues_found": int,
        }
    """
    gdf = parcels_gdf.copy()
    # Ensure valid geometries first
    gdf["geometry"] = gdf.geometry.apply(repair_geometry)

    overlaps = check_overlaps(gdf)
    gaps = check_gaps(gdf, tolerance=1e-6)
    self_ints = check_self_intersections(parcels_gdf)
    duplicates = check_duplicates(gdf)

    issues_found = len(overlaps) + len(gaps) + len(self_ints) + len(duplicates)

    valid_count = sum(1 for g in gdf.geometry if g is not None and g.is_valid and not g.is_empty)

    return {
        "total_parcels": len(gdf),
        "overlaps": overlaps,
        "gaps": gaps,
        "self_intersections": self_ints,
        "duplicates": duplicates,
        "slivers": [],
        "valid_geometry_count": valid_count,
        "issues_found": issues_found,
    }


def check_overlaps(parcels_gdf: gpd.GeoDataFrame) -> List[Tuple[int, int, float]]:
    """Return ``(idx1, idx2, overlap_area)`` for every overlapping pair.

    Uses spatial indexing to limit the search space.
    """
    overlaps: list[tuple[int, int, float]] = []
    geom_list = list(parcels_gdf.geometry)
    idx_list = list(parcels_gdf.index)

    # Use sindex if available
    sindex = parcels_gdf.sindex
    seen = set()

    for i, (idx_a, geom_a) in enumerate(zip(idx_list, geom_list)):
        if geom_a is None or geom_a.is_empty or not geom_a.is_valid:
            continue
        if sindex is not None:
            candidates = list(sindex.intersection(geom_a.bounds))
        else:
            candidates = range(len(geom_list))

        for j in candidates:
            if j <= i:
                continue
            key = (idx_list[i], idx_list[j])
            if key in seen:
                continue
            seen.add(key)

            geom_b = geom_list[j]
            if geom_b is None or geom_b.is_empty or not geom_b.is_valid:
                continue

            if not geom_a.intersects(geom_b):
                continue

            inter = geom_a.intersection(geom_b)
            inter_area = inter.area
            if inter_area > 0:
                overlaps.append((idx_list[i], idx_list[j], inter_area))

    return overlaps


def check_gaps(
    parcels_gdf: gpd.GeoDataFrame,
    tolerance: float = 1e-6,
) -> list:
    """Return gap polygons that exist between parcels.

    The union of all parcels is computed; then small interior rings that are
    likely gaps (rather than courtyards) are extracted based on *tolerance*
    relative to parcel sizes.
    """
    geom_list = [g for g in parcels_gdf.geometry if g is not None and not g.is_empty]
    if not geom_list:
        return []

    union = unary_union(geom_list)
    if not isinstance(union, (Polygon, MultiPolygon)):
        return []

    if union.geom_type == "Polygon":
        polygons = [union]
    else:
        polygons = list(union.geoms)

    gaps = []
    for poly in polygons:
        for interior in poly.interiors:
            hole = Polygon(interior)
            # Gaps: small holes between parcels (not large courtyards)
            if hole.area < tolerance:
                gaps.append(hole.buffer(0))

    return gaps


def check_self_intersections(
    parcels_gdf: gpd.GeoDataFrame,
) -> List[Tuple[int, Any]]:
    """Return ``(idx, invalid_geom)`` for parcels with invalid geometry."""
    issues: list[tuple[int, Any]] = []
    for idx, geom in parcels_gdf.geometry.items():
        if geom is None or geom.is_empty:
            continue
        if not geom.is_valid:
            issues.append((idx, geom))
    return issues


def check_duplicates(
    parcels_gdf: gpd.GeoDataFrame,
) -> List[Tuple[int, int]]:
    """Return index pairs of geometries that are geometrically identical."""
    dups: list[tuple[int, int]] = []
    geom_list = list(parcels_gdf.geometry)
    idx_list = list(parcels_gdf.index)
    seen = set()

    sindex = parcels_gdf.sindex

    for i, (idx_a, geom_a) in enumerate(zip(idx_list, geom_list)):
        if geom_a is None or geom_a.is_empty:
            continue
        if sindex is not None:
            candidates = list(sindex.intersection(geom_a.bounds))
        else:
            candidates = range(len(geom_list))

        for j in candidates:
            if j <= i:
                continue
            key = (i, j)
            if key in seen:
                continue
            seen.add(key)

            geom_b = geom_list[j]
            if geom_b is None or geom_b.is_empty:
                continue

            if geom_a.equals_exact(geom_b, 1e-8):
                dups.append((idx_list[i], idx_list[j]))

    return dups


def check_slivers(
    parcels_gdf: gpd.GeoDataFrame,
    min_area: float,
) -> list:
    """Return indices of parcels whose area is smaller than *min_area*."""
    slivers = []
    for idx, geom in parcels_gdf.geometry.items():
        if geom is None or geom.is_empty:
            continue
        if geom.area < min_area:
            slivers.append(idx)
    return slivers


def repair_topology(
    parcels_gdf: gpd.GeoDataFrame,
) -> Tuple[gpd.GeoDataFrame, list]:
    """Repair topology issues and return ``(repaired_gdf, changes_log)``.

    Changes logged are dicts with keys ``idx``, ``issue``, ``detail``.
    """
    changes: list[dict] = []
    gdf = parcels_gdf.copy()

    # 1. Fix invalid geometries
    for idx, geom in gdf.geometry.items():
        if geom is None or geom.is_empty:
            continue
        if not geom.is_valid:
            repaired = repair_geometry(geom)
            gdf.at[idx, "geometry"] = repaired
            changes.append({"idx": idx, "issue": "self_intersection", "detail": "repaired"})

    # 2. Remove zero-area geometries
    empty_indices = [
        idx for idx, geom in gdf.geometry.items()
        if geom is None or geom.is_empty or geom.area == 0
    ]
    for idx in empty_indices:
        changes.append({"idx": idx, "issue": "empty", "detail": "dropped"})
    gdf = gdf.drop(empty_indices)

    return gdf, changes


def snap_parcel_boundaries(
    parcels_gdf: gpd.GeoDataFrame,
    tolerance: float,
) -> gpd.GeoDataFrame:
    """Snap parcel boundaries to a grid with *tolerance* and repair."""
    gdf = parcels_gdf.copy()
    gdf["geometry"] = gdf.geometry.apply(
        lambda g: _snap_geom(g, tolerance) if g is not None else g
    )
    return gdf


def _snap_geom(geom, tolerance: float):
    """Snap geometry coordinates to grid of *tolerance* spacing."""
    from shapely.geometry import mapping as _mapping
    from shapely.ops import snap as shapely_snap

    def _snap_coord(x, y):
        return (round(x / tolerance) * tolerance, round(y / tolerance) * tolerance)

    mapping_geom = _mapping(geom)

    def _recurse(coords):
        if isinstance(coords[0], (int, float)):
            return _snap_coord(coords[0], coords[1])
        return [_recurse(c) for c in coords]

    mapping_geom["coordinates"] = _recurse(mapping_geom["coordinates"])
    from shapely.geometry import shape as _shape

    snapped = _shape(mapping_geom)
    if not snapped.is_valid:
        snapped = repair_geometry(snapped)
    return snapped
