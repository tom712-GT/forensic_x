from typing import Optional, Dict, Any
from app.forensic.audit_chain import verify_chain
from app.repositories.audit_chain_repository import AuditChainRepository

DISCLAIMER = (
    "A hash chain shows that audit rows from the first chained row onward were not changed, removed "
    "from the middle or reordered after they were written, unless the whole chain was rewritten. "
    "Rows written before the chain started are not verified. Deleting the newest rows is only "
    "detectable with an anchor saved outside this system."
)


class AuditChainService:
    @staticmethod
    def verify(anchor: Optional[str] = None) -> Dict[str, Any]:
        result = verify_chain(AuditChainRepository.iter_rows())
        status = "BROKEN" if result["first_break"] is not None else "OK"

        anchor_check = None
        if anchor is not None:
            anchor_check = AuditChainRepository.check_anchor(anchor)

        return {
            "disclaimer": DISCLAIMER,
            "status": status,
            "total_count": result["total_count"],
            "pre_chain_count": result["pre_chain_count"],
            "chained_count": result["chained_count"],
            "verified_count": result["verified_count"],
            "first_break": result["first_break"],
            "anchor": result["anchor"],
            "anchor_check": anchor_check,
        }
