from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str
    dataset_type: str


class DatasetResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    project_id: int
    name: str
    dataset_type: str
    file_path: str
    metadata_json: Optional[dict] = None
    created_at: datetime


class RasterInfo(BaseModel):
    crs: str
    width: int
    height: int
    bands: int
    resolution: tuple[float, float]
    bounds: tuple[float, float, float, float]
    nodata: Optional[float] = None
    dtype: str


class TileInfo(BaseModel):
    path: int
    row: int
    col: int
    bounds: tuple[float, float, float, float]
    transform_json: dict
