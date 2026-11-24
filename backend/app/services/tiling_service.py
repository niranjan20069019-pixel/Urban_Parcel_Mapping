from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds as window_from_bounds

from app.core.config import settings
from app.core.exceptions import TileError
from app.core.logging import get_logger
from app.gis.raster import inspect_raster

logger = get_logger(__name__)


def tile_raster(
    input_path: str,
    output_dir: str,
    tile_size: int = 512,
    overlap: int = 64,
    fmt: str = "png",
) -> list[dict]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    tile_infos: list[dict] = []
    stride = tile_size - overlap

    with rasterio.open(input_path) as src:
        meta = src.meta.copy()
        crs_str = str(src.crs) if src.crs else None
        transform = src.transform

        n_rows = max(1, (src.height - overlap + stride - 1) // stride)
        n_cols = max(1, (src.width - overlap + stride - 1) // stride)

        for row_idx in range(n_rows):
            for col_idx in range(n_cols):
                r_off = row_idx * stride
                c_off = col_idx * stride
                win_h = min(tile_size, src.height - r_off)
                win_w = min(tile_size, src.width - c_off)

                if win_h <= 0 or win_w <= 0:
                    continue

                window = Window(c_off, r_off, win_w, win_h)
                tile_data = src.read(window=window)
                win_transform = rasterio.windows.transform(window, transform)
                bounds = rasterio.windows.bounds(window, transform)

                tile_name = f"tile_{row_idx}_{col_idx}.{fmt}"
                tile_path = out / tile_name

                tile_meta = meta.copy()
                tile_meta.update(
                    width=win_w,
                    height=win_h,
                    transform=win_transform,
                )

                if fmt == "png":
                    from app.gis.raster import normalize_raster
                    tmp_tif = tile_path.with_suffix(".tif")
                    with rasterio.open(str(tmp_tif), "w", **tile_meta) as dst:
                        dst.write(tile_data)
                    normalize_raster(str(tmp_tif), str(tile_path))
                    tmp_tif.unlink(missing_ok=True)
                else:
                    with rasterio.open(str(tile_path), "w", **tile_meta) as dst:
                        dst.write(tile_data)

                tile_info = {
                    "path": str(tile_path),
                    "row": row_idx,
                    "col": col_idx,
                    "transform": list(win_transform)[:6],
                    "bounds": {
                        "left": bounds[0],
                        "bottom": bounds[1],
                        "right": bounds[2],
                        "top": bounds[3],
                    },
                    "crs": crs_str,
                    "width": win_w,
                    "height": win_h,
                }
                tile_infos.append(tile_info)

        meta_path = out / "tiles_meta.json"
        with open(meta_path, "w") as f:
            json.dump({"tile_size": tile_size, "overlap": overlap, "tiles": tile_infos}, f, indent=2)

    logger.info("Created %d tiles in %s", len(tile_infos), output_dir)
    return tile_infos


def reconstruct_from_tiles(
    tile_dir: str,
    original_shape: tuple[int, int],
    original_transform: rasterio.Affine,
    original_crs: str | None,
) -> np.ndarray:
    tiles_meta_path = Path(tile_dir) / "tiles_meta.json"
    with open(tiles_meta_path) as f:
        meta = json.load(f)

    overlap = meta.get("overlap", 0)
    tile_size = meta.get("tile_size", 512)
    stride = tile_size - overlap

    h, w = original_shape
    mask = np.zeros((h, w), dtype=np.float32)
    count = np.zeros((h, w), dtype=np.float32)

    for tile_info in meta["tiles"]:
        row = tile_info["row"]
        col = tile_info["col"]
        tile_path = tile_info["path"]

        with rasterio.open(tile_path) as src:
            tile_data = src.read(1).astype(np.float32)

        r_off = row * stride
        c_off = col * stride
        th, tw = tile_data.shape

        end_r = min(r_off + th, h)
        end_c = min(c_off + tw, w)
        actual_h = end_r - r_off
        actual_w = end_c - c_off

        if actual_h > 0 and actual_w > 0:
            mask[r_off:end_r, c_off:end_c] += tile_data[:actual_h, :actual_w]
            count[r_off:end_r, c_off:end_c] += 1.0

    valid = count > 0
    mask[valid] /= count[valid]

    logger.info("Reconstructed %dx%d from tiles in %s", w, h, tile_dir)
    return mask


def stitch_predictions(
    tile_dir: str,
    output_path: str,
    original_transform: rasterio.Affine,
    original_crs: str | None,
) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    tiles_meta_path = Path(tile_dir) / "tiles_meta.json"
    with open(tiles_meta_path) as f:
        meta = json.load(f)

    if not meta["tiles"]:
        raise TileError("No tiles found to stitch.")

    max_row = max(t["row"] for t in meta["tiles"])
    max_col = max(t["col"] for t in meta["tiles"])
    tile_size = meta.get("tile_size", 512)
    overlap = meta.get("overlap", 0)
    stride = tile_size - overlap

    h = (max_row + 1) * stride + overlap
    w = (max_col + 1) * stride + overlap

    with rasterio.open(meta["tiles"][0]["path"]) as sample:
        count_bands = sample.count
        sample_dtype = sample.dtypes[0]

    result = np.zeros((count_bands, h, w), dtype=np.float64)
    weight = np.zeros((h, w), dtype=np.float64)

    for tile_info in meta["tiles"]:
        row = tile_info["row"]
        col = tile_info["col"]
        with rasterio.open(tile_info["path"]) as src:
            tile_data = src.read().astype(np.float64)

        r_off = row * stride
        c_off = col * stride
        th, tw = tile_data.shape[1], tile_data.shape[2]

        end_r = min(r_off + th, h)
        end_c = min(c_off + tw, w)
        actual_h = end_r - r_off
        actual_w = end_c - c_off

        if actual_h > 0 and actual_w > 0:
            result[:, r_off:end_r, c_off:end_c] += tile_data[:, :actual_h, :actual_w]
            weight[r_off:end_r, c_off:end_c] += 1.0

    valid = weight > 0
    for b in range(count_bands):
        result[b][valid] /= weight[valid]

    meta_out = rasterio.open(meta["tiles"][0]["path"]).meta.copy()
    meta_out.update(
        height=h,
        width=w,
        transform=original_transform,
        crs=original_crs,
        dtype=sample_dtype,
        count=count_bands,
    )
    with rasterio.open(str(out), "w", **meta_out) as dst:
        dst.write(result.astype(sample_dtype))

    logger.info("Stitched predictions -> %s (%dx%d)", output_path, w, h)
    return str(out)
