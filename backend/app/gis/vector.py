"""Vector I/O utilities for urban parcel mapping."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple, Union

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

_Driver = str
_PathLike = Union[str, Path]
_Bounds = Union[Tuple[float, float, float, float], list[float]]


def load_vector(path: _PathLike, **kwargs) -> gpd.GeoDataFrame:
    """Load a vector file into a GeoDataFrame.

    Supports GeoJSON, GeoPackage, Shapefile, and any format OGR recognises.
    """
    return gpd.read_file(str(path), **kwargs)


def save_vector(
    gdf: gpd.GeoDataFrame,
    path: _PathLike,
    driver: _Driver = "GeoJSON",
    **kwargs,
) -> Path:
    """Write a GeoDataFrame to disk and return the output path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(str(out), driver=driver, **kwargs)
    return out


def reproject_vector(
    gdf: gpd.GeoDataFrame,
    target_crs: Union[str, int],
) -> gpd.GeoDataFrame:
    """Reproject a GeoDataFrame to *target_crs*."""
    return gdf.to_crs(target_crs)


def merge_vector_files(
    paths: List[_PathLike],
    target_crs: Optional[Union[str, int]] = None,
) -> gpd.GeoDataFrame:
    """Merge multiple vector files into a single GeoDataFrame.

    Files are reprojected to *target_crs* if supplied, otherwise to the CRS
    of the first file.
    """
    frames: list[gpd.GeoDataFrame] = []
    for p in paths:
        gdf = load_vector(p)
        if target_crs is not None:
            gdf = gdf.to_crs(target_crs)
        frames.append(gdf)

    if not frames:
        return gpd.GeoDataFrame()

    base_crs = target_crs if target_crs is not None else frames[0].crs
    reprojected = [f.to_crs(base_crs) if f.crs != base_crs else f for f in frames]
    return gpd.GeoDataFrame(pd.concat(reprojected, ignore_index=True), crs=base_crs)


def clip_vector_to_bounds(
    gdf: gpd.GeoDataFrame,
    bounds: _Bounds,
    crs: Union[str, int, None] = None,
) -> gpd.GeoDataFrame:
    """Clip a GeoDataFrame to a bounding box.

    *crs* is the CRS of *bounds*; if omitted the GeoDataFrame's own CRS is
    assumed.
    """
    if crs is not None and gdf.crs is not None and str(gdf.crs) != str(crs):
        gdf = gdf.to_crs(crs)

    bbox_poly = box(*bounds)
    clipped = gpd.clip(gdf, bbox_poly)

    if crs is not None:
        clipped = clipped.to_crs(gdf.crs if gdf.crs is not None else crs)

    return clipped
