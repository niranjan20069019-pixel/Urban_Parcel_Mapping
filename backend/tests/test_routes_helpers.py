"""Runnable checks for the pure helper logic in the API routes (no DB needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shapely.geometry import Polygon

from app.api.routes.upload import _validate_ext
from app.api.routes.comparison import _classify_change, _iou
from app.schemas.comparison import ChangeType


def test_validate_ext():
    _validate_ext("a.tif", {".tif", ".tiff"}, "raster")
    _validate_ext("a.TIFF", {".tif", ".tiff"}, "raster")
    try:
        _validate_ext("a.txt", {".tif"}, "raster")
    except Exception as exc:
        assert "Invalid raster file extension" in str(exc)
    else:
        raise AssertionError("expected rejection of .txt")


def test_classify_change():
    assert _classify_change(0.95, 0.01, 0.1) == ChangeType.UNCHANGED
    assert _classify_change(0.5, 0.1, 5.0) == ChangeType.BOUNDARY_SHIFT
    assert _classify_change(0.1, -0.8, 2.0) == ChangeType.SUBDIVISION
    assert _classify_change(0.1, 2.0, 3.0) == ChangeType.MERGER
    assert _classify_change(0.05, 0.9, 50.0) == ChangeType.NEW
    assert _classify_change(0.2, 0.3, 1.0) == ChangeType.UNCERTAIN


def test_iou():
    a = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    b = Polygon([(1, 0), (3, 0), (3, 2), (1, 2)])
    assert abs(_iou(a, b) - 1 / 3) < 1e-9
    assert _iou(a, Polygon([(10, 10), (12, 10), (12, 12), (10, 12)])) == 0.0


if __name__ == "__main__":
    test_validate_ext()
    test_classify_change()
    test_iou()
    print("route helper checks OK")