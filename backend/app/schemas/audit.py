from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime

class AuditEntryResponse(BaseModel):
    audit_id: int
    timestamp: datetime
    action: str
    outcome: str
    http_status: int
    case_id: Optional[str] = None
    evidence_id: Optional[str] = None
    actor: str
    details: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
