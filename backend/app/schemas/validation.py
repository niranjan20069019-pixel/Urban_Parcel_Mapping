from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ValidationRequest(BaseModel):
    parcel_id: int
    validator: str
    validation_type: str
    status: str
    notes: Optional[str] = None


class ValidationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    parcel_id: int
    validator: str
    validation_type: str
    status: str
    notes: Optional[str] = None
    created_at: datetime


class TopologyIssueResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    issue_type: str
    description: str
    severity: str
    resolved: bool
    geom_json: Optional[dict] = None
