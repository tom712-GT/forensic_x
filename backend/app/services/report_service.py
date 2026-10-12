import datetime
import json
import logging
from typing import Any, Dict, List, Optional

import app.services.timeline_service as ts_mod
from app.services.timeline_service import TimelineService
from app.services.gap_service import GapService
from app.services.correlation_service import CorrelationService
from app.services.audit_chain_service import AuditChainService

from app.repositories.report_repository import ReportRepository

logger = logging.getLogger(__name__)

LIMITATIONS: List[str] = [
    "Timestamps inside files are claims made by the file and are not proof of when events happened.",
    "Calibration is a user-supplied estimate that assumes a constant clock offset.",
    "A gap means no evidence file covers that time; it does not prove deletion or tampering.",
    "Temporal overlap is not proof that cameras show the same event, place or person.",
    "The audit hash chain does not detect a full rewrite or deletion of the newest rows unless an anchor was saved outside this system.",
    "Hashes shown are stored baselines; this report does not re-verify files. Use the verify endpoint for that.",
]

DISCLAIMER: str = (
    "This report summarises stored analysis results for one case. It does not itself prove the authenticity "
    "of any evidence. The report hash only shows that this JSON was not changed after generation, if the hash "
    "was stored somewhere else."
)


def _parse_format(val: Any) -> Optional[str]:
    if not val or not isinstance(val, str):
        return None
    try:
        data = json.loads(val)
        if isinstance(data, dict):
            fmt = data.get("detected_format")
            if isinstance(fmt, str):
                return fmt
    except Exception:
        pass
    return None


def _parse_vendor(val: Any) -> Optional[str]:
    if not val or not isinstance(val, str):
        return None
    try:
        data = json.loads(val)
        if isinstance(data, dict):
            v = data.get("vendor")
            if isinstance(v, str):
                return v
    except Exception:
        pass
    return None


class ReportService:
    @staticmethod
    def build_report(case_id: str, case_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if case_dict is None:
            case_dict = ReportRepository.get_case(case_id)
            if not case_dict:
                raise ValueError("Case not found")

        case_block = {
            "case_id": case_dict["case_id"],
            "case_name": case_dict["case_name"],
            "description": case_dict["description"],
            "status": case_dict["status"],
            "created_at": case_dict["created_at"],
        }

        cap = ts_mod.TIMELINE_MAX_ROWS
        raw_evidence = ReportRepository.get_case_evidence(case_id, cap + 1)
        if len(raw_evidence) > cap:
            evidence_truncated = True
            evidence_rows = raw_evidence[:cap]
        else:
            evidence_truncated = False
            evidence_rows = raw_evidence

        evidence_entries = []
        for r in evidence_rows:
            entry = {
                "evidence_id": r["evidence_id"],
                "evidence_type": r["evidence_type"],
                "status": r["status"],
                "file_size": r["file_size"],
                "stored_size": r["stored_size"],
                "hash_algorithm": r["hash_algorithm"],
                "sha256": r["sha256"],
                "registered_at": r["registered_at"],
                "ingested_at": r["ingested_at"],
                "hashed_at": r["hashed_at"],
                "format": _parse_format(r.get("format_detection")),
                "vendor": _parse_vendor(r.get("vendor_detection")),
                "group_label": r["group_label"] if r.get("group_label") is not None else "DEFAULT",
                "metadata_status": r.get("metadata_status"),
                "calibrated": bool(r.get("calibrated")),
            }
            evidence_entries.append(entry)

        # 1. Timeline section
        tl_res = TimelineService.get_timeline(
            case_id,
            kinds=None,
            time_source=None,
            evidence_id=None,
            start=None,
            end=None,
            limit=1,
            offset=0,
        )
        tl_summary = tl_res["summary"]
        timeline_section = {
            "event_count": tl_summary["event_count"],
            "undated_count": tl_summary["undated_count"],
            "earliest": tl_summary["earliest"],
            "latest": tl_summary["latest"],
            "truncated": tl_summary["truncated"],
        }

        # 2. Calibration section
        cal_refs = ReportRepository.get_calibration_references(case_id)
        calibration_section = {
            "calibrated_evidence_count": len(cal_refs),
            "references": cal_refs,
        }

        # 3. Gaps section
        gaps_res = GapService.get_gaps(case_id, None, 0.0, 1, 0)
        g_sum = gaps_res["summary"]
        gaps_section = {
            "gap_count": g_sum["gap_count"],
            "total_gap_seconds": g_sum["total_gap_seconds"],
            "longest_gap_seconds": g_sum["longest_gap_seconds"],
            "unknown_length_count": len(gaps_res.get("unknown_length", [])),
            "unplaced_count": len(gaps_res.get("unplaced", [])),
            "truncated": g_sum["truncated"],
        }

        # 4. Correlation section
        corr_res = CorrelationService.get_correlation(case_id, None, 0.0, 2, 1, 0)
        c_sum = corr_res["summary"]
        correlation_section = {
            "window_count": c_sum["window_count"],
            "total_overlap_seconds": c_sum["total_overlap_seconds"],
            "longest_overlap_seconds": c_sum["longest_overlap_seconds"],
            "max_simultaneous_groups": c_sum["max_simultaneous_groups"],
            "truncated": c_sum["truncated"],
        }

        # 5. Audit chain section
        ac_res = AuditChainService.verify()
        audit_chain_section = {
            "status": ac_res["status"],
            "total_count": ac_res["total_count"],
            "pre_chain_count": ac_res["pre_chain_count"],
            "chained_count": ac_res["chained_count"],
            "verified_count": ac_res["verified_count"],
            "first_break": ac_res["first_break"],
            "anchor": ac_res["anchor"],
        }

        sections = {
            "timeline": timeline_section,
            "calibration": calibration_section,
            "gaps": gaps_section,
            "correlation": correlation_section,
            "audit_chain": audit_chain_section,
        }

        now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        report = {
            "report_version": "1",
            "generated_at": now_utc,
            "case": case_block,
            "evidence": evidence_entries,
            "evidence_truncated": evidence_truncated,
            "sections": sections,
            "limitations": list(LIMITATIONS),
            "disclaimer": DISCLAIMER,
        }

        return report

    @staticmethod
    def generate_report(case_id: str, case_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return ReportService.build_report(case_id, case_dict)
