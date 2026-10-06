import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def record(
        action: str,
        outcome: str,
        http_status: int,
        case_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record an action in the audit log.
        Best-effort recording: any failure to record is logged but never raised
        to avoid breaking the primary workflow.
        """
        if details is None:
            details = {}
            
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        actor = "UNAUTHENTICATED"
        
        try:
            AuditRepository.insert(
                timestamp=timestamp,
                action=action,
                outcome=outcome,
                http_status=http_status,
                actor=actor,
                details=details,
                case_id=case_id,
                evidence_id=evidence_id
            )
        except Exception:
            logger.exception("Failed to record audit log entry")
