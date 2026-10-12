from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class ReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report: Dict[str, Any]
    report_sha256: str
    algorithm: str
    canonicalization: str


class ReportVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    report: Dict[str, Any]
    report_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")


class ReportVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    computed_sha256: str
    algorithm: str
    disclaimer: str
