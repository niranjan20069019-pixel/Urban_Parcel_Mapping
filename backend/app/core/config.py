from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/urban_cadastral"

    MODEL_CHECKPOINT_DIR: str = "models/checkpoints"
    BUILDING_MODEL_CHECKPOINT: str = "models/checkpoints/building/model.pth"
    ROAD_MODEL_CHECKPOINT: str = "models/checkpoints/road/model.pth"
    LANDUSE_MODEL_CHECKPOINT: str = "models/checkpoints/landuse/model.pth"
    BOUNDARY_MODEL_CHECKPOINT: str = "models/checkpoints/boundary/model.pth"

    TILE_SIZE: int = 512
    TILE_OVERLAP: int = 64

    GPU_ENABLED: bool = False
    DEVICE: str = "auto"
    DEMO_MODE: bool = False

    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = PROJECT_ROOT / "logs"

    SECRET_KEY: str = "change-me-in-production"
    API_PREFIX: str = "/api/v1"

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    ALLOWED_EXTENSIONS: list[str] = [
        ".tif", ".tiff", ".shp", ".geojson", ".gpkg", ".csv", ".jpg", ".png",
    ]

    UPLOAD_DIR: Path = PROJECT_ROOT / "uploads"

    API_KEY: str | None = None

    def ensure_dirs(self) -> None:
        for d in (self.DATA_DIR, self.UPLOAD_DIR, self.LOG_DIR):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def resolved_device(self) -> str:
        if self.DEVICE != "auto":
            return self.DEVICE
        if self.GPU_ENABLED:
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return "cpu"


settings = Settings()
