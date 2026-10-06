from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

def generate_utc_now():
    return datetime.now(timezone.utc)

@dataclass
class RecoveredArtifact:
    evidence_id: str
    case_id: str
    source_offset: int
    recovered_size: int
    detected_type: str
    output_path: str
    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recovery_timestamp: datetime = field(default_factory=generate_utc_now)
    status: str = "RECOVERED"
