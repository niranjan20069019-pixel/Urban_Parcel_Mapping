from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes as rasterio_shapes
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

from app.core.logging import get_logger
from app.gis.geometry import repair_geometry, simplify_geometry
from app.gis.vector import save_vector

logger = get_logger(__name__)


def mask_to_gdf(
    mask: np.ndarray,
    transform: rasterio.Affine,
    crs: str | None,
    class_id: int,
    confidence_mask: np.ndarray | None = None,
) -> gpd.GeoDataFrame:
    binary = (mask == class_id).astype(np.uint8)
    records = []

    for geom_dict, value in rasterio_shapes(binary, mask=binary, transform=transform):
        if value == 0:
            continue
        geom = shape(geom_dict)
        if geom.is_empty:
            continue

        geom = repair_geometry(geom)
        if isinstance(geom, MultiPolygon):
            geom = MultiPolygon([p for p in geom.geoms if not p.is_empty])
        elif isinstance(geom, Polygon):
            geom = Polygon(geom.exterior)
        else:
            continue

        if geom.is_empty:
            continue

        if confidence_mask is not None:
            with rasterio.io.MemoryFile() as mem:
                meta = {
                    "driver": "GTiff",
                    "height": mask.shape[0],
                    "width": mask.shape[1],
                    "count": 1,
                    "dtype": mask.dtype,
                    "crs": crs,
                    "transform": transform,
                }
                with mem.open(**meta) as tmp:
                    tmp.write(confidence_mask.astype(np.float32), 1)
                    from rasterio.mask import mask as rio_mask
                    out_image, _ = rio_mask(tmp, [mapping(geom)], crop=True)
                    conf_val = float(np.mean(out_image[out_image > 0])) if np.any(out_image > 0) else 0.0
        else:
            conf_val = 0.0

        records.append({"geometry": geom, "class_id": class_id, "confidence": conf_val})

    if not records:
        return gpd.GeoDataFrame(columns=["geometry", "class_id", "confidence"], crs=crs)

    return gpd.GeoDataFrame(records, crs=crs)


def clean_polygons(
    gdf: gpd.GeoDataFrame,
    min_area: float = 5.0,
    simplify_tolerance: float = 2.0,
) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf

    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.apply(lambda g: repair_geometry(g) if g else g)
    gdf = gdf[~gdf.geometry.is_empty]
    gdf = gdf[gdf.geometry.area >= min_area]
    gdf["geometry"] = gdf.geometry.apply(
        lambda g: simplify_geometry(g, simplify_tolerance) if g and not g.is_empty else g
    )
    gdf = gdf[~gdf.geometry.is_empty].reset_index(drop=True)
    return gdf


def compute_polygon_attributes(gdf: gpd.GeoDataFrame, crs: str | None = None) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf

    gdf = gdf.copy()
    gdf["area"] = gdf.geometry.area
    gdf["perimeter"] = gdf.geometry.length
    gdf["centroid"] = gdf.geometry.centroid
    gdf["minx"] = gdf.geometry.bounds["minx"]
    gdf["miny"] = gdf.geometry.bounds["miny"]
    gdf["maxx"] = gdf.geometry.bounds["maxx"]
    gdf["maxy"] = gdf.geometry.bounds["maxy"]
    return gdf


def merge_adjacent(gdf: gpd.GeoDataFrame, class_id: int) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf

    subset = gdf[gdf["class_id"] == class_id]
    others = gdf[gdf["class_id"] != class_id]

    if subset.empty:
        return gdf

    merged = unary_union(subset.geometry.tolist())
    if isinstance(merged, Polygon):
        merged = MultiPolygon([merged])

    records = []
    for geom in merged.geoms if hasattr(merged, "geoms") else [merged]:
        if geom.is_empty:
            continue
        records.append({"geometry": geom, "class_id": class_id, "confidence": float(subset["confidence"].mean())})

    merged_gdf = gpd.GeoDataFrame(records, crs=gdf.crs) if records else gpd.GeoDataFrame(columns=gdf.columns, crs=gdf.crs)
    return gpd.GeoDataFrame(
        __import__("pandas").concat([merged_gdf, others], ignore_index=True),
        crs=gdf.crs,
    )


def export_gdf(
    gdf: gpd.GeoDataFrame,
    output_path: str,
    driver: str = "GeoJSON",
) -> str:
    return str(save_vector(gdf, output_path, driver=driver))


def mask_to_gdf_pipeline(
    mask: np.ndarray,
    transform: rasterio.Affine,
    crs: str | None,
    class_id: int,
    output_path: str,
    confidence_mask: np.ndarray | None = None,
    min_area: float = 5.0,
    simplify_tolerance: float = 2.0,
) -> str:
    gdf = mask_to_gdf(mask, transform, crs, class_id, confidence_mask)
    gdf = clean_polygons(gdf, min_area=min_area, simplify_tolerance=simplify_tolerance)
    gdf = compute_polygon_attributes(gdf, crs)
    return export_gdf(gdf, output_path)
