from pydantic import BaseModel
from datetime import datetime

class RecoveredArtifactResponse(BaseModel):
    artifact_id: str
    evidence_id: str
    case_id: str
    source_offset: int
    recovered_size: int
    detected_type: str
    recovery_timestamp: datetime
    status: str
