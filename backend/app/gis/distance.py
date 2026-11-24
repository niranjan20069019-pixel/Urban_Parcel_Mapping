"""Distance and boundary-metric utilities for urban parcel mapping."""

from __future__ import annotations

from typing import Union

import numpy as np
from shapely.geometry import MultiPoint, Point, shape
from shapely.ops import nearest_points
from shapely.validation import make_valid

Geom = Union[Point, "Polygon", "MultiPolygon"]  # noqa: F821 – type hint only


def _ensure_valid(geom):
    if not geom.is_valid:
        geom = make_valid(geom)
    return geom


def _sample_boundary_distance(geom1: Geom, geom2: Geom) -> float:
    """Mean Euclidean distance from every boundary point of *geom1* to the
    nearest point on *geom2* (and vice-versa), averaged.

    Uses a sampled boundary approach for performance on large geometries.
    """
    geom1 = _ensure_valid(geom1)
    geom2 = _ensure_valid(geom2)
    pts1 = MultiPoint(_sample_boundary(geom1))
    pts2 = MultiPoint(_sample_boundary(geom2))
    d12 = _mean_dist_to_geom(pts1, geom2)
    d21 = _mean_dist_to_geom(pts2, geom1)
    return (d12 + d21) / 2.0


def boundary_displacement(geom1: Geom, geom2: Geom) -> float:
    """Mean distance between the boundaries of two geometries."""
    return _sample_boundary_distance(geom1, geom2)


def _sample_boundary(geom, n: int = 200) -> list[Point]:
    """Return *n* points evenly sampled along the geometry boundary."""
    boundary = geom.boundary
    if boundary.is_empty:
        return []
    if boundary.geom_type == "Point":
        return [boundary]
    if boundary.geom_type == "MultiLineString":
        coords = []
        for line in boundary.geoms:
            coords.extend(_sample_line(line, n))
        return coords
    return _sample_line(boundary, n)


def _sample_line(line, n: int) -> list[Point]:
    length = line.length
    if length == 0:
        return [Point(line.coords[0])]
    return [line.interpolate(i / max(n - 1, 1), normalized=True) for i in range(n)]


def _mean_dist_to_geom(points, target_geom) -> float:
    """Average distance from each point in *points* to *target_geom*."""
    dists = []
    target_boundary = target_geom.boundary
    for pt in points.geoms:
        d = pt.distance(target_boundary)
        dists.append(d)
    return float(np.mean(dists)) if dists else 0.0


def hausdorff_distance(geom1: Geom, geom2: Geom) -> float:
    """Hausdorff distance between two geometries (Shapely built-in)."""
    geom1 = _ensure_valid(geom1)
    geom2 = _ensure_valid(geom2)
    return float(geom1.hausdorff_distance(geom2))


def centroid_distance(geom1: Geom, geom2: Geom) -> float:
    """Euclidean distance between centroids."""
    geom1 = _ensure_valid(geom1)
    geom2 = _ensure_valid(geom2)
    return float(geom1.centroid.distance(geom2.centroid))


def polygon_iou(geom1: Geom, geom2: Geom) -> float:
    """Intersection-over-Union of two polygons (returns 0 for empty overlap)."""
    geom1 = _ensure_valid(geom1)
    geom2 = _ensure_valid(geom2)
    inter = geom1.intersection(geom2).area
    union = geom1.union(geom2).area
    return inter / union if union > 0 else 0.0


def area_difference(geom1: Geom, geom2: Geom) -> float:
    """Signed area difference: area(geom1 \\ geom2) - area(geom2 \\ geom1) in
    square metres.

    Both geometries must share a projected CRS for the value to be in
    meaningful units.  When planar, the result is in the CRS linear unit
    squared.
    """
    geom1 = _ensure_valid(geom1)
    geom2 = _ensure_valid(geom2)
    a_only_1 = geom1.difference(geom2).area
    a_only_2 = geom2.difference(geom1).area
    return float(a_only_1 - a_only_2)


def point_to_polygon_distance(point: Point, polygon: Geom) -> float:
    """Minimum distance from *point* to *polygon* boundary (0 if inside)."""
    polygon = _ensure_valid(polygon)
    point = _ensure_valid(point)
    if polygon.contains(point):
        return 0.0
    return float(point.distance(polygon.boundary))


def points_to_polygon_distance(points_gdf, polygon: Geom) -> dict:
    """Return {min, max, mean} distances from a GeoDataFrame of points to *polygon*."""
    polygon = _ensure_valid(polygon)
    dists = [point_to_polygon_distance(pt, polygon) for pt in points_gdf.geometry]
    if not dists:
        return {"min": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "min": float(np.min(dists)),
        "max": float(np.max(dists)),
        "mean": float(np.mean(dists)),
    }
