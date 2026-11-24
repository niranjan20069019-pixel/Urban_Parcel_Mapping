"""Test tiling operations."""
import pytest
import numpy as np
import rasterio
from rasterio.transform import from_bounds
import tempfile
import os

@pytest.fixture
def large_geotiff():
    path = tempfile.mktemp(suffix='.tif')
    data = np.random.randint(0, 255, (3, 1024, 1024), dtype=np.uint8)
    transform = from_bounds(77.5, 12.5, 77.6, 12.6, 1024, 1024)
    with rasterio.open(path, 'w', driver='GTiff', height=1024, width=1024,
                       count=3, dtype='uint8', crs='EPSG:4326',
                       transform=transform) as dst:
        dst.write(data)
    yield path
    os.unlink(path)

def test_tile_count(large_geotiff, tmp_path):
    from app.services.tiling_service import tile_raster
    tiles = tile_raster(large_geotiff, str(tmp_path), tile_size=512, overlap=64)
    assert len(tiles) > 0
    assert all('path' in t for t in tiles)
