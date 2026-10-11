from typing import List
from pydantic import BaseModel, ConfigDict
from app.schemas.gaps import UnknownLengthItem, UnplacedItem


class WindowMemberItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_label: str
    evidence_ids: List[str]


class WindowItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window_id: str
    start: str
    end: str
    length_seconds: float
    groups: List[str]
    group_count: int
    members: List[WindowMemberItem]
    uncertain: bool


class CorrelationGroupItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_label: str
    interval_count: int


class CorrelationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window_count: int
    total_overlap_seconds: float
    longest_overlap_seconds: float
    max_simultaneous_groups: int
    truncated: bool


class CorrelationPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int
    offset: int
    total: int


class CorrelationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    disclaimer: str
    groups: List[CorrelationGroupItem]
    windows: List[WindowItem]
    unknown_length: List[UnknownLengthItem]
    unplaced: List[UnplacedItem]
    summary: CorrelationSummary
    page: CorrelationPage
