from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class EvidenceCreate(BaseModel):
    """
    Schema for registering new evidence.
    """
    # Bad metadata at registration weakens traceability later.
    model_config = ConfigDict(str_strip_whitespace=True)

    original_filename: str = Field(..., min_length=1, max_length=255, description="Original filename of the evidence.")
    evidence_type: str = Field(..., min_length=1, max_length=100, description="Type of the evidence, e.g., DVR_FORENSIC_IMAGE.")
    file_size: int = Field(..., ge=0, description="File size in bytes.")
    description: Optional[str] = Field(None, description="Optional description of the evidence.")
    source: Optional[str] = Field(None, description="Optional source or origin of the evidence.")
    acquisition_time: Optional[datetime] = Field(None, description="Optional time when the evidence was acquired.")

class DetectionResult(BaseModel):
    model_config = ConfigDict(extra='allow')
    detected_at: datetime

class EvidenceResponse(BaseModel):
    """
    Schema for returning Evidence data in responses.
    """
    evidence_id: str
    case_id: str
    original_filename: str
    evidence_type: str
    file_size: int
    description: Optional[str] = None
    source: Optional[str] = None
    acquisition_time: Optional[datetime] = None
    status: str
    registered_at: datetime
    stored_size: Optional[int] = None
    size_matches_declared: Optional[bool] = None
    ingested_at: Optional[datetime] = None
    hash_algorithm: Optional[str] = None
    sha256: Optional[str] = None
    hashed_at: Optional[datetime] = None
    format_detection: Optional[DetectionResult] = None
    vendor_detection: Optional[DetectionResult] = None

class EvidenceVerifyResponse(BaseModel):
    """
    Schema for returning the result of a hash verification.
    """
    evidence_id: str
    hash_algorithm: str
    baseline_sha256: str
    computed_sha256: str
    match: bool
    verified_at: datetime
