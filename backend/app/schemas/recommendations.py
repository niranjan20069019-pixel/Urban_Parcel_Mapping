from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel


class RecommendationAction(str, Enum):
    ACCEPT_PRELIMINARY = "accept_preliminary"
    SURVEYOR_REVIEW = "surveyor_review"
    GNSS_VERIFICATION = "gnss_verification"
    FIELD_SURVEY = "field_survey"
    BOUNDARY_REVIEW = "boundary_review"
    TOPOLOGY_REPAIR = "topology_repair"
    INVESTIGATE_SUBDIVISION = "investigate_subdivision"
    INVESTIGATE_MERGER = "investigate_merger"
    INVESTIGATE_NEW_PARCEL = "investigate_new_parcel"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    parcel_id: int
    action: RecommendationAction
    priority: Priority
    reason: str
    evidence_json: Optional[dict] = None
    created_at: datetime


class RecommendationList(BaseModel):
    recommendations: list[RecommendationResponse]
    counts_by_priority: dict[str, int]
