from pydantic import BaseModel, Field, StrictStr
from typing import Optional, List, Dict, Any

class CalibrationCreate(BaseModel):
    device_time: StrictStr = Field(...)
    reference_time: StrictStr = Field(...)
    uncertainty_seconds: float = Field(..., ge=0, le=31536000, allow_inf_nan=False)
    note: Optional[str] = Field(None, max_length=500)

class CalibrationRecord(BaseModel):
    reference_id: str
    evidence_id: str
    case_id: str
    device_time: str
    reference_time: str
    offset_seconds: float
    uncertainty_seconds: float
    note: Optional[str]
    flags: List[str]
    entered_at: str
    entered_by: str
    superseded_at: Optional[str]
    status: str
    
class CalibrationHistory(BaseModel):
    evidence_id: str
    disclaimer: str
    active: Optional[CalibrationRecord]
    history: List[CalibrationRecord]

class CalibratedItem(BaseModel):
    event_id: str
    evidence_id: str
    kind: str
    original_timestamp: str
    flags: List[str]
    correction_status: str
    calibration: Optional[Dict[str, Any]]
    corrected: Optional[Dict[str, Any]]
    effective_timestamp: str

class CalibratedTimelineSummary(BaseModel):
    item_count: int
    by_status: Dict[str, int]
    truncated: bool

class CalibratedTimelineResponse(BaseModel):
    case_id: str
    disclaimer: str
    items: List[CalibratedItem]
    summary: CalibratedTimelineSummary
