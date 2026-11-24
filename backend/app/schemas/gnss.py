from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class GnssPointCreate(BaseModel):
    point_id: str
    latitude: float
    longitude: float
    height: Optional[float] = None
    accuracy: Optional[float] = None
    crs: str = "EPSG:4326"
    source: Optional[str] = None


class GnssPointResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    point_id: str
    latitude: float
    longitude: float
    height: Optional[float] = None
    accuracy: Optional[float] = None
    crs: str
    source: Optional[str] = None
    created_at: datetime


class GnssImportRequest(BaseModel):
    file_path: str
    crs: str = "EPSG:4326"


class GnssValidationResult(BaseModel):
    point_id: str
    nearest_parcel_id: Optional[int] = None
    distance_to_boundary: Optional[float] = None
    accuracy_flag: bool
