from typing import Optional, List
from pydantic import BaseModel, StrictStr, Field, ConfigDict


class EvidenceGroupUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    group_label: StrictStr = Field(..., min_length=1, max_length=64)


class EvidenceGroupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    case_id: str
    group_label: str
    is_default: bool
    set_at: Optional[str] = None


class GapItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gap_id: str
    group_label: str
    start: str
    end: str
    length_seconds: float
    length_min_seconds: float
    length_max_seconds: float
    certainty: str
    before_evidence_id: str
    after_evidence_id: str


class GroupSummaryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_label: str
    interval_count: int
    gap_count: int


class UnknownLengthItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    group_label: str
    reason: str
    start: str


class UnplacedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    group_label: str
    reason: str


class GapsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gap_count: int
    total_gap_seconds: float
    longest_gap_seconds: float
    truncated: bool


class GapsPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int
    offset: int
    total: int


class GapsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    disclaimer: str
    groups: List[GroupSummaryItem]
    gaps: List[GapItem]
    unknown_length: List[UnknownLengthItem]
    unplaced: List[UnplacedItem]
    summary: GapsSummary
    page: GapsPage
