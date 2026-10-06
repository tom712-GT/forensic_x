from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field
import uuid

def generate_utc_now():
    return datetime.now(timezone.utc)

@dataclass
class Evidence:
    """
    Represents forensic evidence in FORENSIC-X.
    A case represents the investigation context.
    Evidence belongs to a specific case.
    Original evidence must be preserved/read-only.
    This first implementation stores metadata only.
    Actual file ingestion, hashing, parsing and analysis will be implemented later.
    """
    case_id: str
    original_filename: str
    evidence_type: str
    file_size: int
    description: Optional[str] = None
    source: Optional[str] = None
    acquisition_time: Optional[datetime] = None
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "REGISTERED"
    registered_at: datetime = field(default_factory=generate_utc_now)
    stored_size: Optional[int] = None
    size_matches_declared: Optional[bool] = None
    ingested_at: Optional[datetime] = None
    stored_path: Optional[str] = None
    hash_algorithm: Optional[str] = None
    sha256: Optional[str] = None
    hashed_at: Optional[datetime] = None
    format_detection: Optional[dict] = None
    vendor_detection: Optional[dict] = None
    filesystem_analysis: Optional[dict] = None
