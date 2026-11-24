"""Test CRS operations."""
import pytest
from shapely.geometry import Point, box

def test_validate_crs():
    from app.gis.crs import validate_crs
    assert validate_crs("EPSG:4326") is True
    assert validate_crs("EPSG:32644") is True
    assert validate_crs("INVALID") is False

def test_get_crs_epsg():
    from app.gis.crs import get_crs_epsg
    assert get_crs_epsg("EPSG:4326") == 4326

def test_reproject_geometry():
    from app.gis.crs import reproject_geometry
    pt = Point(77.5, 12.5)
    result = reproject_geometry(pt, "EPSG:4326", "EPSG:32643")
    assert result is not None
    assert result.x != pt.x

def test_ensure_utm():
    from app.gis.crs import ensure_utm_crs
    # bounds: (minx, miny, maxx, maxy) around Kathmandu (77.5E, 12.5N)
    crs = ensure_utm_crs((77.4, 12.4, 77.6, 12.6))
    assert crs is not None
    assert crs.is_projected
