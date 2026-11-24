from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject as rio_reproject

from app.core.logging import get_logger
from app.gis.raster import normalize_raster

logger = get_logger(__name__)


def preprocess_raster(
    input_path: str,
    output_path: str,
    normalize: bool = True,
    target_crs: str | None = None,
) -> dict:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(input_path) as src:
        data = src.read().astype(np.float64)
        meta = src.meta.copy()
        transform = src.transform
        crs = src.crs

    if target_crs and crs and str(crs) != target_crs:
        with rasterio.open(input_path) as src:
            transform, width, height = calculate_default_transform(
                src.crs, target_crs, src.width, src.height, *src.bounds
            )
            meta.update(crs=target_crs, transform=transform, width=width, height=height)
            data = np.empty((src.count, height, width), dtype=np.float64)
            for i in range(1, src.count + 1):
                rio_reproject(
                    source=src.read(i),
                    destination=data[i - 1],
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )

    if normalize:
        for band_idx in range(data.shape[0]):
            band = data[band_idx]
            valid = band[np.isfinite(band)]
            if valid.size > 0:
                vmin, vmax = valid.min(), valid.max()
                if vmax > vmin:
                    data[band_idx] = (band - vmin) / (vmax - vmin) * 255.0
                else:
                    data[band_idx] = 128.0
        meta.update(dtype="uint8")
        data = data.astype(np.uint8)

    meta.update(count=data.shape[0])
    with rasterio.open(str(out), "w", **meta) as dst:
        dst.write(data)

    logger.info("Preprocessed raster: %s (normalize=%s, crs=%s)", output_path, normalize, target_crs)
    return {
        "output_path": str(out),
        "width": data.shape[-1],
        "height": data.shape[-2],
        "bands": data.shape[0],
        "dtype": str(data.dtype),
    }


def create_pyramid(input_path: str) -> str:
    out = Path(input_path)
    with rasterio.open(input_path) as src:
        overviews = [2, 4, 8, 16]
        src.build_overviews(overviews, Resampling.nearest)
    logger.info("Created pyramids for %s", input_path)
    return str(out)


def enhance_image(input_path: str, output_path: str) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(input_path) as src:
        meta = src.meta.copy()
        enhanced = np.empty((src.count, src.height, src.width), dtype=np.float64)

        for i in range(1, src.count + 1):
            band = src.read(i).astype(np.float64)
            vmin, vmax = np.percentile(band[band != (src.nodata or 0)], [2, 98]) if np.any(band != (src.nodata or 0)) else (0, 1)
            if vmax > vmin:
                band = np.clip((band - vmin) / (vmax - vmin), 0, 1) * 255.0
            else:
                band = np.full_like(band, 128.0)
            enhanced[i - 1] = band

        meta.update(dtype="uint8")
        with rasterio.open(str(out), "w", **meta) as dst:
            dst.write(enhanced.astype(np.uint8))

    logger.info("Enhanced image: %s", output_path)
    return str(out)
