import json
from typing import List, Optional
from fastapi import APIRouter, Query
from app.schemas.audit import AuditEntryResponse
from app.repositories.audit_repository import AuditRepository

router = APIRouter(tags=["audit"])

@router.get("/api/audit-log", response_model=List[AuditEntryResponse])
def get_audit_log(
    case_id: Optional[str] = Query(None),
    evidence_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Retrieve audit log entries.
    Plain GET reads are not audited.
    """
    rows = AuditRepository.list_entries(case_id=case_id, evidence_id=evidence_id, limit=limit)
    
    entries = []
    for r in rows:
        # details is JSON text in DB, we must parse it to dict for response
        det = json.loads(r["details"])
        entries.append({
            "audit_id": r["audit_id"],
            "timestamp": r["timestamp"],
            "action": r["action"],
            "outcome": r["outcome"],
            "http_status": r["http_status"],
            "case_id": r["case_id"],
            "evidence_id": r["evidence_id"],
            "actor": r["actor"],
            "details": det
        })
    return entries
