"""Geometry operations for urban parcel mapping."""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple, Union

import numpy as np
import rasterio
from shapely.affinity import affine_transform
from shapely.geometry import MultiPolygon, Point, Polygon, box, mapping, shape
from shapely.ops import linemerge, polygonize, unary_union
from shapely.validation import make_valid
from rasterio.features import shapes as rasterio_shapes
from rasterio.features import rasterize as rio_rasterize


# ---------------------------------------------------------------------------
# Repair / validation
# ---------------------------------------------------------------------------

def repair_geometry(geom):
    """Fix invalid geometries (close gaps, resolve self-intersections)."""
    if geom is None or geom.is_empty:
        return geom
    if geom.is_valid:
        return geom
    repaired = make_valid(geom)
    if not repaired.is_valid:
        repaired = repaired.buffer(0)
    return repaired


def simplify_geometry(geom, tolerance: float):
    """Simplify geometry with *tolerance* in CRS units."""
    if geom is None or geom.is_empty:
        return geom
    simplified = geom.simplify(tolerance, preserve_topology=True)
    if not simplified.is_valid:
        simplified = make_valid(simplified)
    return simplified


# ---------------------------------------------------------------------------
# Mask / raster to polygon conversion
# ---------------------------------------------------------------------------

def polygonize_mask(mask: np.ndarray, transform) -> list:
    """Convert a binary mask to shapely geometries with affine transforms.

    Each geometry is returned as ``(polygon, affine_transform_params)`` where
    *affine_transform_params* is a list ``[a, b, c, d, e, f]`` suitable for
    ``shapely.affinity.affine_transform`` to convert the pixel-space polygon
    into CRS coordinates.  Geometries live in pixel (column, row) space.
    """
    from rasterio.features import shapes as rasterio_shapes

    polys = []
    has_data = mask > 0
    mask_uint8 = has_data.astype(np.uint8)
    for geom_dict, value in rasterio_shapes(mask_uint8, mask=mask_uint8):
        if value == 0:
            continue
        geom = shape(geom_dict)
        if geom.is_empty:
            continue
        affine_params = [
            transform.a, transform.b,
            transform.d, transform.e,
            transform.c, transform.f,
        ]
        polys.append((geom, affine_params))

    return polys


def mask_to_polygons(
    mask: np.ndarray,
    transform,
    min_area: float = 10.0,
    simplify_tolerance: float = 1.0,
) -> list:
    """Convert a mask to ``(polygon, confidence)`` pairs.

    Cells with value > 0 are treated as foreground.  The confidence is the
    mean value of the original mask inside each polygon.  Polygons smaller
    than *min_area* (in CRS units squared) are dropped.
    """
    has_data = mask > 0
    polys: list[tuple[Polygon, float]] = []
    for geom_dict, value in rasterio_shapes(
        has_data.astype(np.uint8), mask=has_data.astype(np.uint8), transform=transform
    ):
        if value == 0:
            continue
        geom = shape(geom_dict)
        if geom.is_empty or not isinstance(geom, Polygon):
            continue
        geom = repair_geometry(geom)
        if simplify_tolerance > 0:
            geom = simplify_geometry(geom, simplify_tolerance)
        if geom.area < min_area:
            continue

        sampled = rio_rasterize(
            [(geom, 1)], out_shape=has_data.shape, transform=transform
        ).astype(bool)
        inside = mask[sampled & has_data]
        confidence = float(np.mean(inside)) if inside.size else 0.0
        polys.append((geom, confidence))

    return polys


# ---------------------------------------------------------------------------
# Contours
# ---------------------------------------------------------------------------

def extract_contours(mask: np.ndarray, transform) -> list:
    """Extract contour lines from *mask* and return as shapely LineStrings.

    Uses OpenCV for contour detection.  Contours are returned as shapely
    geometries with coordinates in CRS units.
    """
    try:
        import cv2
    except ImportError:
        raise ImportError("OpenCV (cv2) is required for contour extraction")

    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    from shapely.geometry import LineString

    lines = []
    for contour in contours:
        if len(contour) < 2:
            continue
        pixel_coords = contour.squeeze()
        if pixel_coords.ndim != 2 or pixel_coords.shape[1] != 2:
            continue
        # convert pixel -> CRS coordinates
        xs, ys = rasterio.transform.xy(
            transform, pixel_coords[:, 1], pixel_coords[:, 0]
        )
        line = LineString(zip(xs, ys))
        lines.append(line)

    return lines


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def compute_area_km2(geom, crs) -> float:
    """Area in square kilometres, reprojecting to an equal-area CRS if needed."""
    if geom is None or geom.is_empty:
        return 0.0

    from pyproj import CRS as ProjCRS

    crs_obj = ProjCRS(crs) if not isinstance(crs, ProjCRS) else crs
    if crs_obj.is_geographic:
        # Reproject to UTM for area
        from .crs import ensure_utm_crs, reproject_geometry

        utm = ensure_utm_crs(geom.bounds)
        geom = reproject_geometry(geom, crs, utm)
        area_m2 = geom.area
    else:
        area_m2 = geom.area

    return area_m2 / 1_000_000.0


def compute_perimeter_km(geom, crs) -> float:
    """Perimeter in kilometres."""
    if geom is None or geom.is_empty:
        return 0.0

    from pyproj import CRS as ProjCRS

    crs_obj = ProjCRS(crs) if not isinstance(crs, ProjCRS) else crs
    if crs_obj.is_geographic:
        from .crs import ensure_utm_crs, reproject_geometry

        utm = ensure_utm_crs(geom.bounds)
        geom = reproject_geometry(geom, crs, utm)

    return geom.length / 1_000.0


def compute_centroid(geom) -> Point:
    """Return the centroid of the geometry."""
    if geom is None or geom.is_empty:
        return Point()
    return geom.centroid


def compute_bbox(geom) -> tuple:
    """Return ``(minx, miny, maxx, maxy)``."""
    if geom is None or geom.is_empty:
        return (0.0, 0.0, 0.0, 0.0)
    return geom.bounds


# ---------------------------------------------------------------------------
# Set operations
# ---------------------------------------------------------------------------

def merge_polygons(polys: Sequence) -> Union[MultiPolygon, Polygon]:
    """Merge a sequence of polygons into a single geometry."""
    valid = [p for p in polys if p is not None and not p.is_empty]
    if not valid:
        return MultiPolygon()
    merged = unary_union(valid)
    return merged


def split_polygon_by_lines(polygon: Polygon, lines) -> list:
    """Split *polygon* by *lines* (LineString or MultiLineString).

    Returns a list of resulting Polygons.
    """
    from shapely.ops import split as ops_split

    if polygon is None or polygon.is_empty:
        return []
    splitter = (
        linemerge(lines)
        if hasattr(lines, "geoms")
        else lines
    )
    result = ops_split(polygon, splitter)
    return [g for g in result.geoms if g.geom_type == "Polygon"]


# ---------------------------------------------------------------------------
# Topology helpers
# ---------------------------------------------------------------------------

def fix_self_intersections(geom):
    """Resolve self-intersections by buffering by zero."""
    if geom is None or geom.is_empty:
        return geom
    if not geom.is_valid:
        geom = make_valid(geom)
    if hasattr(geom, "buffer"):
        fixed = geom.buffer(0)
        if not fixed.is_valid:
            fixed = make_valid(fixed)
        return fixed
    return geom


def snap_to_grid(geom, tolerance: float):
    """Snap all coordinates to a grid with the given *tolerance*."""
    if geom is None or geom.is_empty:
        return geom

    def _snap(x, y, z=None):
        sx = round(x / tolerance) * tolerance
        sy = round(y / tolerance) * tolerance
        return (sx, sy) if z is None else (sx, sy, z)

    snapped = _apply_coords(geom, _snap)
    if not snapped.is_valid:
        snapped = repair_geometry(snapped)
    return snapped


def _apply_coords(geom, func):
    """Apply *func* to every coordinate in *geom*."""
    from shapely.geometry import mapping as _mapping

    mapping_geom = _mapping(geom)

    def _recurse(coords):
        if isinstance(coords[0], (int, float)):
            return func(*coords)
        return [_recurse(c) for c in coords]

    mapping_geom["coordinates"] = _recurse(mapping_geom["coordinates"])
    return shape(mapping_geom)


def remove_holes(geom, max_hole_area_ratio: float = 0.01) -> Polygon:
    """Remove holes whose area is smaller than *max_hole_area_ratio * total area*."""
    if geom is None or geom.is_empty:
        return geom
    if geom.geom_type == "MultiPolygon":
        return MultiPolygon(
            [remove_holes(p, max_hole_area_ratio) for p in geom.geoms]
        )
    if geom.geom_type != "Polygon":
        return geom

    total_area = geom.area
    if total_area == 0:
        return geom

    exterior = geom.exterior
    kept_holes = []
    for interior in geom.interiors:
        hole_area = Polygon(interior).area
        if hole_area / total_area >= max_hole_area_ratio:
            kept_holes.append(interior)

    return Polygon(exterior, kept_holes)
