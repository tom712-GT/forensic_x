from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any

class TimelineSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: str
    field: str
    origin: Optional[str] = None
    byte_offset: Optional[int] = None

class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    timestamp: str
    kind: str
    time_source: str
    evidence_id: str
    source: TimelineSource
    raw_value: Any
    flags: List[str]
    detail: dict

class TimelineUndated(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    kind: str
    time_source: str
    evidence_id: str
    source: TimelineSource
    raw_value: Any
    reason: str
    detail: dict

class TimelineSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_count: int
    undated_count: int
    earliest: Optional[str] = None
    latest: Optional[str] = None
    by_kind: Dict[str, int]
    by_source: Dict[str, int]
    truncated: bool

class TimelinePage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int
    offset: int
    total: int

class TimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    disclaimer: str
    events: List[TimelineEvent]
    undated: List[TimelineUndated]
    summary: TimelineSummary
    page: TimelinePage
