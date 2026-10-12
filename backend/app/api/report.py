import logging
from fastapi import APIRouter, HTTPException

from app.forensic.report_hash import compute_report_hash
from app.repositories.report_repository import ReportRepository
from app.schemas.report import ReportResponse, ReportVerifyRequest, ReportVerifyResponse
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["report"])

VERIFY_DISCLAIMER = (
    "A valid result means the report content matches the supplied hash. It does not prove the report is "
    "accurate or that the hash itself was not replaced."
)


@router.get("/api/cases/{case_id}/report", response_model=ReportResponse)
def get_report(case_id: str):
    from app.api.evidence import _audit, _raise_audit

    case_obj = ReportRepository.get_case(case_id)
    if not case_obj:
        _raise_audit(
            action="REPORT_GENERATE",
            outcome="NOT_FOUND",
            status_code=404,
            reason="UNKNOWN_CASE",
            case_id=case_id,
            evidence_id=None,
            detail_msg="Case not found",
        )

    try:
        report = ReportService.build_report(case_id, case_obj)
        report_sha256 = compute_report_hash(report)
        _audit(
            action="REPORT_GENERATE",
            outcome="SUCCESS",
            http_status=200,
            case_id=case_id,
            evidence_id=None,
            details={"report_sha256": report_sha256},
        )
        return {
            "report": report,
            "report_sha256": report_sha256,
            "algorithm": "SHA-256",
            "canonicalization": "JSON with sorted keys, separators (',', ':'), ASCII escapes, UTF-8, SHA-256",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error while generating report for case %s", case_id)
        _raise_audit(
            action="REPORT_GENERATE",
            outcome="ERROR",
            status_code=500,
            reason="INTERNAL_ERROR",
            case_id=case_id,
            evidence_id=None,
            detail_msg="Internal error while generating report",
        )


@router.post("/api/reports/verify", response_model=ReportVerifyResponse)
def verify_report(req: ReportVerifyRequest):
    computed_sha256 = compute_report_hash(req.report)
    is_valid = computed_sha256 == req.report_sha256
    return {
        "valid": is_valid,
        "computed_sha256": computed_sha256,
        "algorithm": "SHA-256",
        "disclaimer": VERIFY_DISCLAIMER,
    }
