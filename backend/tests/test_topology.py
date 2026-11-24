"""Test topology validation."""
import pytest
import geopandas as gpd
from shapely.geometry import Polygon, box


def test_validate_clean_parcels():
    from app.gis.topology import validate_parcel_topology
    parcels = gpd.GeoDataFrame({
        'id': [1, 2],
        'geometry': [Polygon([(0,0),(1,0),(1,1),(0,1)]),
                     Polygon([(1,0),(2,0),(2,1),(1,1)])]
    }, crs='EPSG:4326')
    result = validate_parcel_topology(parcels)
    assert 'issues_found' in result
    assert result['issues_found'] == 0
    assert result['total_parcels'] == 2


def test_check_self_intersections():
    from app.gis.topology import check_self_intersections
    valid = gpd.GeoDataFrame({'geometry': [box(0,0,1,1)]}, crs='EPSG:4326')
    issues = check_self_intersections(valid)
    assert len(issues) == 0
