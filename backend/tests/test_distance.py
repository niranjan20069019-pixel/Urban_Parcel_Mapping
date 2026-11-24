"""Test distance metrics."""
import pytest
from shapely.geometry import Polygon

def test_polygon_iou():
    from app.gis.distance import polygon_iou
    a = Polygon([(0,0),(2,0),(2,2),(0,2)])
    b = Polygon([(1,1),(3,1),(3,3),(1,3)])
    iou = polygon_iou(a, b)
    assert 0 < iou < 1

def test_centroid_distance():
    from app.gis.distance import centroid_distance
    a = Polygon([(0,0),(1,0),(1,1),(0,1)])
    b = Polygon([(5,5),(6,5),(6,6),(5,6)])
    dist = centroid_distance(a, b)
    assert dist > 0

def test_identical_polygons_iou():
    from app.gis.distance import polygon_iou
    a = Polygon([(0,0),(1,0),(1,1),(0,1)])
    iou = polygon_iou(a, a)
    assert abs(iou - 1.0) < 0.01
