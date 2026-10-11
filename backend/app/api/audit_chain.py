from typing import Optional
from fastapi import APIRouter, Query
from app.schemas.audit_chain import AuditVerifyResponse
from app.services.audit_chain_service import AuditChainService

router = APIRouter(tags=["audit"])


@router.get("/api/audit-log/verify", response_model=AuditVerifyResponse)
def verify_audit_log(
    anchor: Optional[str] = Query(None, pattern=r"^[0-9a-f]{64}$")
) -> AuditVerifyResponse:
    """
    Verify the cryptographic integrity of the audit log hash chain.
    Read-only, not audited.
    """
    return AuditChainService.verify(anchor=anchor)
