"""Test geometry operations."""
import pytest
import numpy as np
from shapely.geometry import Polygon, box
from rasterio.transform import from_bounds

def test_repair_geometry():
    from app.gis.geometry import repair_geometry
    valid = box(0, 0, 1, 1)
    result = repair_geometry(valid)
    assert result.is_valid

def test_compute_area():
    from app.gis.geometry import compute_area_km2
    # 1 degree square at equator roughly
    poly = box(0, 0, 1, 1)
    area = compute_area_km2(poly, "EPSG:4326")
    assert area > 0

def test_simplify_geometry():
    from app.gis.geometry import simplify_geometry
    # Complex wavy polygon (may simplify into MultiPolygon — must stay valid)
    coords = [(i/10, np.sin(i/10)) for i in range(100)]
    coords.append(coords[0])
    poly = Polygon(coords)
    simplified = simplify_geometry(poly, 0.1)
    assert simplified.is_valid
    assert not simplified.is_empty
