"""Spatial indexing utilities for urban parcel mapping."""

from __future__ import annotations

from typing import List, Optional, Tuple, Union

import geopandas as gpd
from shapely.geometry import box

_Bounds = Union[Tuple[float, float, float, float], list[float]]


def create_spatial_index(gdf: gpd.GeoDataFrame):
    """Create and return an rtree spatial index from a GeoDataFrame.

    The returned index supports ``intersection(bbox)`` queries that yield
    integer positional indices into the GeoDataFrame.
    """
    from rtree import index as rtree_index

    idx = rtree_index.Index()
    for i, geom in enumerate(gdf.geometry):
        if geom is None or geom.is_empty:
            continue
        idx.insert(i, geom.bounds)
    return idx


def query_bbox(
    gdf: gpd.GeoDataFrame,
    bounds: _Bounds,
) -> gpd.GeoDataFrame:
    """Return the subset of *gdf* whose geometries intersect *bounds*.

    Uses native geopandas spatial indexing when available, falls back to
    manual bounding-box intersection.
    """
    if gdf.sindex is not None:
        try:
            hits = list(gdf.sindex.intersection(bounds))
            return gdf.iloc[hits].copy()
        except Exception:
            pass

    bbox = box(*bounds)
    mask = gdf.geometry.intersects(bbox)
    return gdf[mask].copy()


def query_nearest(
    gdf: gpd.GeoDataFrame,
    geometry,
    k: int = 5,
) -> gpd.GeoDataFrame:
    """Return the *k* features nearest to *geometry*.

    Uses a brute-force distance scan which is fine for moderate-sized
    GeoDataFrames; for very large sets consider a prepared spatial index.
    """
    distances = gdf.geometry.distance(geometry)
    nearest_idx = distances.nsmallest(k).index
    return gdf.loc[nearest_idx].copy()


def bulk_insert_gdf(
    gdf: gpd.GeoDataFrame,
    table_name: str,
    engine,
    if_exists: str = "replace",
    chunk_size: int = 500,
) -> int:
    """Insert a GeoDataFrame into a PostGIS (or any SQLAlchemy-supported) table.

    Returns the number of rows inserted.
    """
    import pandas as pd

    write_gdf = gdf.copy()
    geom_col = write_gdf.geometry.name if write_gdf.geometry.name != "geometry" else "geometry"

    write_gdf.to_postgis(
        table_name,
        engine,
        if_exists=if_exists,
        index=False,
        chunksize=chunk_size,
    )
    return len(write_gdf)
