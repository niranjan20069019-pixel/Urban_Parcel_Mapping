"""CRS handling utilities for urban parcel mapping."""

from __future__ import annotations

from typing import Tuple, Union

from pyproj import CRS, Transformer
from shapely.geometry import box, mapping
from shapely.ops import transform as shapely_transform

CRS_EXTENSIONS: dict[str, str] = {
    "WGS84": "EPSG:4326",
    "WGS 84": "EPSG:4326",
    "GPS": "EPSG:4326",
    "UTM North": "EPSG:32632",
    "UTM South": "EPSG:32732",
    "Web Mercator": "EPSG:3857",
    "Pseudo-Mercator": "EPSG:3857",
    "NAD83": "EPSG:4269",
    "NAD27": "EPSG:4267",
    "ETRS89": "EPSG:4258",
    "GCJ-02": "EPSG:4490",
    "BD-09": "EPSG:4547",
    "Indian 1975": "EPSG:24047",
    "ITRF2000": "EPSG:4919",
    "ITRF2014": "EPSG:9000",
    "Nepal": "EPSG:32645",
    "Kathmandu": "EPSG:2426",
}

_Bounds = Union[Tuple[float, float, float, float], list[float]]


def validate_crs(crs: Union[str, int, CRS]) -> bool:
    """Return True if *crs* can be parsed into a valid CRS."""
    try:
        CRS(crs)
        return True
    except Exception:
        return False


def get_crs_epsg(crs: Union[str, int, CRS]) -> int:
    """Return the EPSG code for *crs*, or 0 if unavailable."""
    try:
        c = CRS(crs)
    except Exception:
        return 0
    epsg = c.to_epsg()
    return epsg if epsg else 0


def _to_crs(crs: Union[str, int, CRS]) -> CRS:
    """Resolve a CRS shorthand/name to a CRS object."""
    if isinstance(crs, CRS):
        return crs
    key = str(crs).strip()
    if key.upper().startswith("EPSG:"):
        return CRS(key)
    resolved = CRS_EXTENSIONS.get(key)
    if resolved:
        return CRS(resolved)
    return CRS(crs)


def reproject_geometry(
    geom,
    from_crs: Union[str, int, CRS],
    to_crs: Union[str, int, CRS],
):
    """Reproject a shapely geometry between two CRS."""
    src = _to_crs(from_crs)
    dst = _to_crs(to_crs)
    transformer = Transformer.from_crs(src, dst, always_xy=True)
    return shapely_transform(transformer.transform, geom)


def reproject_bounds(
    bounds: _Bounds,
    from_crs: Union[str, int, CRS],
    to_crs: Union[str, int, CRS],
) -> Tuple[float, float, float, float]:
    """Reproject a bounding box (minx, miny, maxx, maxy) between two CRS."""
    minx, miny, maxx, maxy = bounds
    src = _to_crs(from_crs)
    dst = _to_crs(to_crs)
    transformer = Transformer.from_crs(src, dst, always_xy=True)
    x1, y1 = transformer.transform(minx, miny)
    x2, y2 = transformer.transform(maxx, maxy)
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _utm_epsg_for_lon(lon: float) -> int:
    zone = int((lon + 180) / 6) + 1
    return 32600 + zone


def ensure_utm_crs(bounds_wgs84: _Bounds) -> CRS:
    """Auto-detect the UTM CRS from WGS84 bounds (midpoint longitude).

    Returns a pyproj.CRS for the UTM zone covering the center of the given
    bounding box.  Assumes northern hemisphere; for southern use the EPSG
    327xx variant.
    """
    minx, miny, maxx, maxy = bounds_wgs84
    mid_lon = (minx + maxx) / 2.0
    mid_lat = (miny + maxy) / 2.0
    epsg = _utm_epsg_for_lon(mid_lon)
    if mid_lat < 0:
        epsg += 100
    return CRS(f"EPSG:{epsg}")
