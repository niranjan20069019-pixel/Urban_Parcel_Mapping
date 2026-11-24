"""Test raster operations with synthetic data."""
import pytest
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
import tempfile
import os

@pytest.fixture
def synthetic_geotiff():
    """Create a temporary GeoTIFF for testing."""
    with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as f:
        path = f.name
    
    data = np.random.randint(0, 255, (3, 100, 100), dtype=np.uint8)
    transform = from_bounds(77.5, 12.5, 77.6, 12.6, 100, 100)
    
    with rasterio.open(path, 'w', driver='GTiff', height=100, width=100,
                       count=3, dtype='uint8', crs='EPSG:4326',
                       transform=transform) as dst:
        dst.write(data)
    
    yield path
    os.unlink(path)

def test_inspect_raster(synthetic_geotiff):
    from app.gis.raster import inspect_raster
    info = inspect_raster(synthetic_geotiff)
    assert info['width'] == 100
    assert info['height'] == 100
    assert info['bands'] == 3
    assert 'EPSG:4326' in str(info['crs'])
