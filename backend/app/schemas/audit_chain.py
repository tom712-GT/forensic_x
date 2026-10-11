from typing import Optional
from pydantic import BaseModel, ConfigDict


class FirstBreak(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audit_id: int
    reason: str


class Anchor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audit_id: int
    row_hash: str


class AnchorCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matched: bool
    audit_id: Optional[int] = None
    rows_after_anchor: Optional[int] = None


class AuditVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    disclaimer: str
    status: str
    total_count: int
    pre_chain_count: int
    chained_count: int
    verified_count: int
    first_break: Optional[FirstBreak] = None
    anchor: Optional[Anchor] = None
    anchor_check: Optional[AnchorCheck] = None
