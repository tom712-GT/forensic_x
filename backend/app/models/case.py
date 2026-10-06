from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field
import uuid

def generate_utc_now():
    return datetime.now(timezone.utc)

@dataclass
class Case:
    """
    Represents a forensic investigation case in FORENSIC-X.
    Evidence (videos, images) will be attached to a specific case.
    """
    case_name: str
    description: Optional[str] = None
    case_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=generate_utc_now)
    status: str = "OPEN"
