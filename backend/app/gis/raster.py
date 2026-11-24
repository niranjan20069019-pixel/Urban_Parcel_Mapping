"""Raster I/O utilities for urban parcel mapping."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds as rasterio_from_bounds
from rasterio.warp import calculate_default_transform, reproject as rio_reproject

_ResamplingName = str
_PathLike = Union[str, Path]

_RESAMPLING_MAP: dict[str, Resampling] = {
    "nearest": Resampling.nearest,
    "bilinear": Resampling.bilinear,
    "cubic": Resampling.cubic,
    "cubic_spline": Resampling.cubic_spline,
    "lanczos": Resampling.lanczos,
    "average": Resampling.average,
    "mode": Resampling.mode,
    "max": Resampling.max,
    "min": Resampling.min,
    "med": Resampling.med,
    "sum": Resampling.sum,
}


def _resolve_resampling(name: _ResamplingName) -> Resampling:
    key = name.lower().strip()
    if key not in _RESAMPLING_MAP:
        raise ValueError(
            f"Unknown resampling method '{name}'. "
            f"Choose from: {', '.join(_RESAMPLING_MAP)}"
        )
    return _RESAMPLING_MAP[key]


def inspect_raster(path: _PathLike) -> dict:
    """Return metadata about a raster file.

    Keys: crs, width, height, bands, resolution, bounds, nodata, transform, dtype.
    """
    with rasterio.open(str(path)) as src:
        res = src.res
        return {
            "crs": str(src.crs) if src.crs else None,
            "width": src.width,
            "height": src.height,
            "bands": src.count,
            "resolution": {"x": res[0], "y": res[1]},
            "bounds": {
                "left": src.bounds.left,
                "bottom": src.bounds.bottom,
                "right": src.bounds.right,
                "top": src.bounds.top,
            },
            "nodata": src.nodata,
            "transform": list(src.transform),
            "dtype": [src.dtypes[i] for i in range(src.count)],
        }


def read_raster_window(
    path: _PathLike,
    window: Tuple[int, int, int, int],
    band: Optional[int] = None,
) -> Tuple[np.ndarray, rasterio.Affine]:
    """Read a pixel window ``(row_off, col_off, height, width)`` from a raster.

    Returns ``(data_array, window_transform)``.
    """
    row_off, col_off, height, width = window
    win = rasterio.windows.Window(col_off, row_off, width, height)

    with rasterio.open(str(path)) as src:
        data = src.read(band, window=win) if band else src.read(window=win)
        win_transform = rasterio.windows.transform(win, src.transform)

    return data, win_transform


def read_raster_bounds(path: _PathLike) -> dict:
    """Return the bounding box and CRS of a raster file."""
    with rasterio.open(str(path)) as src:
        return {
            "left": src.bounds.left,
            "bottom": src.bounds.bottom,
            "right": src.bounds.right,
            "top": src.bounds.top,
            "crs": str(src.crs) if src.crs else None,
        }


def reproject_raster(
    src_path: _PathLike,
    dst_path: _PathLike,
    target_crs: Union[str, int],
    resampling: _ResamplingName = "nearest",
) -> Path:
    """Reproject a raster to *target_crs* and write to *dst_path*.

    Returns the output path.
    """
    out = Path(dst_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    method = _resolve_resampling(resampling)

    with rasterio.open(str(src_path)) as src:
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update(
            crs=target_crs,
            transform=transform,
            width=width,
            height=height,
        )

        with rasterio.open(str(out), "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                src_band = src.read(i)
                dst_band = np.empty((height, width), dtype=src.dtypes[i - 1])
                rio_reproject(
                    source=src_band,
                    destination=dst_band,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=method,
                )
                dst.write(dst_band, i)

    return out


def normalize_raster(
    path: _PathLike,
    output_path: _PathLike,
    bands: Optional[List[int]] = None,
) -> Path:
    """Normalize raster values to 0-255 (uint8) per-band using min-max scaling.

    Nodata pixels remain nodata.  If *bands* is given only those band indices
    (1-based) are written; otherwise all bands are included.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(str(path)) as src:
        band_indices = bands or list(range(1, src.count + 1))
        kwargs = src.meta.copy()
        out_nodata = 0 if src.nodata is not None else None
        kwargs.update(count=len(band_indices), dtype="uint8", nodata=out_nodata)

        with rasterio.open(str(out), "w", **kwargs) as dst:
            for write_idx, band_num in enumerate(band_indices, start=1):
                data = src.read(band_num).astype(np.float64)
                nodata = src.nodata

                if nodata is not None:
                    nodata_mask = data == nodata
                else:
                    nodata_mask = np.zeros_like(data, dtype=bool)

                valid = data[~nodata_mask]
                if valid.size == 0:
                    normalized = np.zeros_like(data, dtype=np.uint8)
                else:
                    vmin, vmax = valid.min(), valid.max()
                    if vmax == vmin:
                        normalized = np.full_like(data, 128, dtype=np.uint8)
                    else:
                        normalized = ((data - vmin) / (vmax - vmin) * 255.0)
                        normalized = normalized.astype(np.uint8)

                if nodata is not None:
                    normalized[nodata_mask] = 0

                dst.write(normalized, write_idx)

    return out


def compute_ndsm(
    dsm_path: _PathLike,
    dtm_path: _PathLike,
    output_path: _PathLike,
) -> Path:
    """Compute nDSM = DSM - DTM.

    The DTM is reprojected/resampled to match the DSM grid if their CRS or
    resolutions differ.  Output is float32.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(str(dsm_path)) as dsm, rasterio.open(str(dtm_path)) as dtm:
        dtm_data = np.empty((dsm.height, dsm.width), dtype=np.float32)
        rio_reproject(
            source=rasterio.band(dtm, 1),
            destination=dtm_data,
            src_transform=dtm.transform,
            src_crs=dtm.crs,
            dst_transform=dsm.transform,
            dst_crs=dsm.crs,
            resampling=Resampling.bilinear,
        )

        dsm_data = dsm.read(1).astype(np.float32)

        ndsm = dsm_data - dtm_data

        if dsm.nodata is not None:
            ndsm[dsm_data == dsm.nodata] = np.nan
        if dtm.nodata is not None:
            ndsm[dtm_data == dtm.nodata] = np.nan

        kwargs = dsm.meta.copy()
        kwargs.update(dtype="float32", count=1, nodata=np.nan)

        with rasterio.open(str(out), "w", **kwargs) as dst:
            dst.write(ndsm, 1)

    return out


def compute_slope(dem_path: _PathLike, output_path: _PathLike) -> Path:
    """Compute slope in degrees from a DEM using numpy gradient.

    Cell sizes are derived from the raster resolution.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(str(dem_path)) as src:
        dem = src.read(1).astype(np.float64)
        res_x, res_y = src.res

        grad_y, grad_x = np.gradient(dem, res_y, res_x)
        slope_rad = np.arctan(np.sqrt(grad_x**2 + grad_y**2))
        slope_deg = np.degrees(slope_rad)

        if src.nodata is not None:
            slope_deg[dem == src.nodata] = np.nan

        kwargs = src.meta.copy()
        kwargs.update(dtype="float32", count=1, nodata=np.nan)

        with rasterio.open(str(out), "w", **kwargs) as dst:
            dst.write(slope_deg.astype(np.float32), 1)

    return out


def compute_roughness(dem_path: _PathLike, output_path: _PathLike) -> Path:
    """Compute surface roughness as the standard deviation of elevation in a
    3x3 moving window.

    Cells at the edge use whatever valid neighbours are available.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(str(dem_path)) as src:
        dem = src.read(1).astype(np.float64)

        rows, cols = dem.shape
        roughness = np.zeros((rows, cols), dtype=np.float32)

        for r in range(rows):
            for c in range(cols):
                r_min, r_max = max(0, r - 1), min(rows, r + 2)
                c_min, c_max = max(0, c - 1), min(cols, c + 2)
                window = dem[r_min:r_max, c_min:c_max].ravel()
                window = window[~np.isnan(window)]
                if src.nodata is not None:
                    window = window[window != src.nodata]
                roughness[r, c] = float(np.std(window)) if len(window) > 1 else 0.0

        kwargs = src.meta.copy()
        kwargs.update(dtype="float32", count=1, nodata=0.0)

        with rasterio.open(str(out), "w", **kwargs) as dst:
            dst.write(roughness, 1)

    return out
