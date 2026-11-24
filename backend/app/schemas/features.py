from typing import Optional

from pydantic import BaseModel


class BuildingResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    area: float
    perimeter: float
    confidence: float
    height: Optional[float] = None
    geom_json: dict


class RoadResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    road_class: str
    width: Optional[float] = None
    length: float
    confidence: float
    geom_json: dict
    centerline_json: Optional[dict] = None


class LanduseResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    landuse_class: str
    area: float
    confidence: float
    geom_json: dict


class BoundaryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    boundary_type: str
    confidence: float
    geom_json: dict


class FeatureCollectionResponse(BaseModel):
    type: str = "FeatureCollection"
    features: list[dict]
