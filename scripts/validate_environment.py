"""Validate that all required dependencies are installed.

Checks: Python, PyTorch, CUDA, GDAL, Rasterio, GeoPandas, Shapely,
PostgreSQL/PostGIS (optional), Node (optional), and the data directory
skeleton.  Exit code 0 when required deps are found.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

REQUIRED = {
    'fastapi': 'fastapi',
    'uvicorn': 'uvicorn',
    'rasterio': 'rasterio',
    'geopandas': 'geopandas',
    'shapely': 'shapely',
    'pyproj': 'pyproj',
    'sqlalchemy': 'sqlalchemy',
    'geoalchemy2': 'geoalchemy2',
    'numpy': 'numpy',
    'torch': 'torch',
    'torchvision': 'torchvision',
    'cv2': 'opencv-python-headless',
    'yaml': 'pyyaml',
}

OPTIONAL = {
    'timm': 'timm',
    'smp': 'segmentation-models-pytorch',
    'skimage': 'scikit-image',
    'ultralytics': 'ultralytics (YOLO adapter)',
    'xgboost': 'xgboost (confidence adapter)',
    'transformers': 'transformers (Mask2Former)',
}


def _check_db() -> tuple[str, bool]:
    try:
        import asyncpg
    except ImportError:
        return "asyncpg not installed", False
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/urban_cadastral",
    ).replace("postgresql+asyncpg://", "postgresql://")
    try:
        import asyncio
        async def _try():
            conn = await asyncpg.connect(url, timeout=2)
            await conn.close()
            return True
        return ("reachable", asyncio.run(_try()))
    except Exception as exc:
        return f"unreachable ({type(exc).__name__})", False


def _check_cuda() -> str:
    try:
        import torch
        if not torch.cuda.is_available():
            return "not available (CPU-only torch)"
        return f"available ({torch.cuda.get_device_name(0)})"
    except Exception as exc:
        return f"error ({exc})"


def _check_node() -> tuple[str, bool]:
    try:
        out = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        return (out.stdout.strip(), out.returncode == 0)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"not found ({type(exc).__name__})", False


def _check_data_dirs() -> tuple[str, bool]:
    from app.core.config import settings
    settings.ensure_dirs()
    expected = ["raw", "processed", "tiles", "predictions", "vectors", "parcels", "gnss", "exports"]
    present = [d for d in expected if (settings.DATA_DIR / d).exists()]
    return f"{len(present)}/{len(expected)} present", len(present) == len(expected)


def check() -> bool:
    print("=== Environment Validation ===\n")
    print(f"Python: {sys.version.split()[0]}\n")

    all_ok = True
    ok = fail = 0
    for module, pkg in REQUIRED.items():
        try:
            mod = importlib.import_module(module)
            ver = getattr(mod, "__version__", "unknown")
            print(f"  [OK] {pkg} ({ver})")
            ok += 1
        except ImportError:
            print(f"  [MISSING] {pkg} — pip install {pkg}")
            fail += 1
            all_ok = False

    print(f"\nCUDA: {_check_cuda()}")

    print("\nOptional:")
    for module, pkg in OPTIONAL.items():
        try:
            importlib.import_module(module)
            print(f"  [OK] {pkg}")
        except ImportError:
            print(f"  [NOT INSTALLED] {pkg}")

    db_status, db_ok = _check_db()
    print(f"\nPostgreSQL/PostGIS: {db_status}")
    if not db_ok:
        all_ok = False

    node_ver, node_ok = _check_node()
    print(f"Node.js: {node_ver}")
    if not node_ok:
        print("  Frontend build requires Node.js >= 18")

    data_status, data_ok = _check_data_dirs()
    print(f"Data directories: {data_status}")
    if not data_ok:
        all_ok = False

    print(f"\n{ok} required libs found, {fail} missing")
    return all_ok


if __name__ == "__main__":
    sys.exit(0 if check() else 1)