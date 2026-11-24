from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ChangeType(str, Enum):
    UNCHANGED = "unchanged"
    BOUNDARY_SHIFT = "boundary_shift"
    SUBDIVISION = "subdivision"
    MERGER = "merger"
    NEW = "new"
    REMOVED = "removed"
    CONFLICT = "conflict"
    UNCERTAIN = "uncertain"


class ComparisonResult(BaseModel):
    old_parcel_id: int
    new_parcel_id: int
    iou: float
    area_difference: float
    centroid_distance: float
    boundary_displacement: float
    hausdorff_distance: float
    change_type: ChangeType


class ComparisonResponse(BaseModel):
    results: list[ComparisonResult]
    summary: dict


class ChangeClassification(BaseModel):
    parcel_id: int
    change_type: ChangeType
    confidence: float
    evidence_json: Optional[dict] = None
    recommendation: str
