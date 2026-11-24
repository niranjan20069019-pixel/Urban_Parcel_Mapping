from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel


class ParcelStatus(str, Enum):
    OLD = "old"
    AI_GENERATED = "ai_generated"
    SURVEYOR_EDITED = "surveyor_edited"
    GNSS_VALIDATED = "gnss_validated"
    FINAL_VALIDATED = "final_validated"


class ParcelCreate(BaseModel):
    geom_wkt: Optional[str] = None
    geom_json: Optional[dict] = None
    status: ParcelStatus = ParcelStatus.AI_GENERATED
    metadata: Optional[dict] = None


class ParcelResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    project_id: int
    version: int
    status: ParcelStatus
    area: float
    perimeter: float
    confidence: float
    change_type: Optional[str] = None
    geom_json: dict
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class ParcelListResponse(BaseModel):
    parcels: list[ParcelResponse]
    total: int


class ParcelVersion(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    version: int
    status: ParcelStatus
    area: float
    geom_json: dict
    created_at: datetime


class ParcelEditRequest(BaseModel):
    geom_json: dict
    notes: Optional[str] = None
    editor: str


class ConfidenceBreakdown(BaseModel):
    ai_agreement: float
    gis_agreement: float
    boundary_evidence: float
    gnss_agreement: float
    topology_validity: float
    area_plausibility: float
    weighted_score: float
