import json
import datetime
import logging
from typing import Optional
from fastapi import HTTPException

from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.case_repository import CaseRepository
from app.repositories.gap_repository import GapRepository
from app.services.calibration_service import CalibrationService
from app.forensic.timeline_builder import parse_to_datetime, format_timestamp
from app.forensic.gap_analysis import (
    MAX_DURATION_SECONDS,
    validate_duration,
    compute_gaps,
    make_gap_id,
)

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "A gap means no evidence file in this case covers that time. It does not prove deletion, "
    "overwriting or tampering. Times are container claims, corrected only where a calibration exists. "
    "A file is assumed to start at its creation_time and to last its duration. Files with unknown "
    "length or time are listed separately and are not used."
)


class GapService:

    @staticmethod
    def set_group(evidence_id: str, group_label: str):
        from app.api.evidence import _audit, _raise_audit

        ev = EvidenceRepository.get_by_id(evidence_id)
        if not ev:
            _raise_audit(
                "GROUP_SET",
                "NOT_FOUND",
                404,
                "UNKNOWN_EVIDENCE",
                evidence_id=evidence_id,
                detail_msg="Evidence not found",
            )

        stripped = group_label.strip()
        if stripped == "":
            _raise_audit(
                "GROUP_SET",
                "REJECTED",
                400,
                "INVALID_GROUP_LABEL",
                evidence_id=evidence_id,
                case_id=ev.case_id,
                detail_msg="Invalid group_label",
            )

        now = datetime.datetime.now(datetime.timezone.utc)
        set_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            GapRepository.set_evidence_group(
                evidence_id=evidence_id,
                case_id=ev.case_id,
                group_label=stripped,
                set_at=set_at,
                set_by="UNAUTHENTICATED",
            )
        except Exception:
            logger.exception("Error saving group")
            _raise_audit(
                "GROUP_SET",
                "ERROR",
                500,
                "INTERNAL_ERROR",
                evidence_id=evidence_id,
                case_id=ev.case_id,
                detail_msg="Internal error while saving group",
            )

        _audit(
            "GROUP_SET",
            "SUCCESS",
            200,
            case_id=ev.case_id,
            evidence_id=evidence_id,
            details={},
        )

        return {
            "evidence_id": evidence_id,
            "case_id": ev.case_id,
            "group_label": stripped,
            "is_default": False,
            "set_at": set_at,
        }

    @staticmethod
    def get_group(evidence_id: str):
        ev = EvidenceRepository.get_by_id(evidence_id)
        if not ev:
            raise HTTPException(status_code=404, detail="Evidence not found")

        row = GapRepository.get_evidence_group(evidence_id)
        if row:
            return {
                "evidence_id": evidence_id,
                "case_id": ev.case_id,
                "group_label": row["group_label"],
                "is_default": False,
                "set_at": row["set_at"],
            }
        return {
            "evidence_id": evidence_id,
            "case_id": ev.case_id,
            "group_label": "DEFAULT",
            "is_default": True,
            "set_at": None,
        }

    @staticmethod
    def get_gaps(
        case_id: str,
        group: Optional[str] = None,
        min_gap_seconds: float = 0.0,
        limit: int = 100,
        offset: int = 0,
    ):
        case_obj = CaseRepository.get_by_id(case_id)
        if not case_obj:
            raise HTTPException(status_code=404, detail="Case not found")

        import app.services.timeline_service as ts_mod

        cap = ts_mod.TIMELINE_MAX_ROWS

        calibrated = CalibrationService.get_calibrated_times(case_id, None)

        calibrated_by_evidence = {}
        for item in calibrated.get("items", []):
            if item.get("kind") == "CONTAINER_CREATION_TIME":
                eid = item["evidence_id"]
                if eid not in calibrated_by_evidence:
                    calibrated_by_evidence[eid] = item

        ev_ids_raw = GapRepository.get_case_evidence_ids(case_id, cap + 1)
        truncated_query2 = len(ev_ids_raw) > cap
        ev_ids = ev_ids_raw[:cap]

        groups_map = GapRepository.get_case_evidence_groups(case_id)

        meta_rows_raw = GapRepository.get_case_metadata_extractions(case_id, cap + 1)
        truncated_query4 = len(meta_rows_raw) > cap
        meta_rows = meta_rows_raw[:cap]

        metadata_by_evidence = {}
        for row in meta_rows:
            sid = row["subject_id"]
            try:
                parsed = json.loads(row["result"])
            except Exception:
                parsed = {}
            metadata_by_evidence[sid] = parsed

        is_truncated = (
            truncated_query2
            or truncated_query4
            or bool(calibrated.get("summary", {}).get("truncated", False))
        )

        unknown_length = []
        unplaced = []
        intervals_by_group = {}

        for eid in ev_ids:
            group_label = groups_map.get(eid, "DEFAULT")
            if group is not None and group_label != group:
                continue

            # Duration extraction
            meta_data = metadata_by_evidence.get(eid)
            has_dur_field = False
            dur_val = None
            if isinstance(meta_data, dict):
                fields = meta_data.get("fields")
                if isinstance(fields, list):
                    for f in fields:
                        if isinstance(f, dict) and f.get("field") == "duration":
                            has_dur_field = True
                            dur_val = f.get("interpreted_value")
                            break

            if not has_dur_field:
                dur_float, dur_reason = None, "NO_DURATION"
            else:
                dur_float, dur_reason = validate_duration(dur_val)

            # Calibration check
            if eid not in calibrated_by_evidence:
                unplaced.append({
                    "evidence_id": eid,
                    "group_label": group_label,
                    "reason": "NO_CREATION_TIME",
                })
                continue

            item = calibrated_by_evidence[eid]
            if item.get("correction_status") == "OUT_OF_RANGE":
                unplaced.append({
                    "evidence_id": eid,
                    "group_label": group_label,
                    "reason": "CALIBRATION_OUT_OF_RANGE",
                })
                continue

            start_nom_dt, _ = parse_to_datetime(item["effective_timestamp"])
            if start_nom_dt is None:
                unplaced.append({
                    "evidence_id": eid,
                    "group_label": group_label,
                    "reason": "NO_CREATION_TIME",
                })
                continue

            if item.get("correction_status") == "CALIBRATED":
                start_earliest_dt, _ = parse_to_datetime(
                    item["corrected"]["earliest"]
                )
                start_latest_dt, _ = parse_to_datetime(
                    item["corrected"]["latest"]
                )
            else:
                start_earliest_dt = start_nom_dt
                start_latest_dt = start_nom_dt

            if dur_reason is not None:
                unknown_length.append({
                    "evidence_id": eid,
                    "group_label": group_label,
                    "reason": dur_reason,
                    "start": format_timestamp(start_nom_dt),
                })
                continue

            try:
                dur_td = datetime.timedelta(seconds=dur_float)
                end_nom_dt = start_nom_dt + dur_td
                end_earliest_dt = start_earliest_dt + dur_td
                end_latest_dt = start_latest_dt + dur_td

                if not (
                    1000 <= end_nom_dt.year <= 9999
                    and 1000 <= end_earliest_dt.year <= 9999
                    and 1000 <= end_latest_dt.year <= 9999
                ):
                    raise OverflowError("Time out of range")
            except (OverflowError, ValueError):
                unknown_length.append({
                    "evidence_id": eid,
                    "group_label": group_label,
                    "reason": "TIME_OUT_OF_RANGE",
                    "start": format_timestamp(start_nom_dt),
                })
                continue

            if group_label not in intervals_by_group:
                intervals_by_group[group_label] = []

            intervals_by_group[group_label].append({
                "evidence_id": eid,
                "start": start_nom_dt,
                "start_earliest": start_earliest_dt,
                "start_latest": start_latest_dt,
                "duration_seconds": dur_float,
            })

        all_included_gaps = []
        group_summary_list = []

        for grp_label in sorted(intervals_by_group.keys()):
            grp_intervals = intervals_by_group[grp_label]
            raw_gaps = compute_gaps(grp_intervals)

            grp_included_gaps = []
            for g in raw_gaps:
                if (
                    g["length_seconds"] >= min_gap_seconds
                    and g["length_seconds"] > 0
                ):
                    gap_id = make_gap_id(
                        grp_label,
                        g["before_evidence_id"],
                        g["after_evidence_id"],
                    )
                    grp_included_gaps.append({
                        "gap_id": gap_id,
                        "group_label": grp_label,
                        "start": format_timestamp(g["start"]),
                        "end": format_timestamp(g["end"]),
                        "length_seconds": float(g["length_seconds"]),
                        "length_min_seconds": float(g["length_min_seconds"]),
                        "length_max_seconds": float(g["length_max_seconds"]),
                        "certainty": g["certainty"],
                        "before_evidence_id": g["before_evidence_id"],
                        "after_evidence_id": g["after_evidence_id"],
                        "_start_dt": g["start"],
                    })

            all_included_gaps.extend(grp_included_gaps)
            group_summary_list.append({
                "group_label": grp_label,
                "interval_count": len(grp_intervals),
                "gap_count": len(grp_included_gaps),
            })

        all_included_gaps.sort(
            key=lambda x: (x["group_label"], x["_start_dt"], x["gap_id"])
        )
        for g in all_included_gaps:
            del g["_start_dt"]

        unknown_length.sort(key=lambda x: (x["group_label"], x["evidence_id"]))
        unplaced.sort(key=lambda x: (x["group_label"], x["evidence_id"]))

        gap_count = len(all_included_gaps)
        if gap_count > 0:
            total_gap_seconds = round(
                sum(g["length_seconds"] for g in all_included_gaps), 6
            )
            longest_gap_seconds = max(
                g["length_seconds"] for g in all_included_gaps
            )
        else:
            total_gap_seconds = 0.0
            longest_gap_seconds = 0.0

        summary = {
            "gap_count": gap_count,
            "total_gap_seconds": total_gap_seconds,
            "longest_gap_seconds": longest_gap_seconds,
            "truncated": is_truncated,
        }

        paged_gaps = all_included_gaps[offset : offset + limit]
        page = {
            "limit": limit,
            "offset": offset,
            "total": gap_count,
        }

        return {
            "case_id": case_id,
            "disclaimer": DISCLAIMER,
            "groups": group_summary_list,
            "gaps": paged_gaps,
            "unknown_length": unknown_length,
            "unplaced": unplaced,
            "summary": summary,
            "page": page,
        }
