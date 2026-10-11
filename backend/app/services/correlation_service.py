from typing import Optional
from fastapi import HTTPException

from app.repositories.case_repository import CaseRepository
from app.services.gap_service import GapService
from app.forensic.timeline_builder import format_timestamp
from app.forensic.correlation import compute_windows, make_window_id

DISCLAIMER = (
    "Temporal overlap means files from different groups claim to cover the same time. It is not proof "
    "that they show the same event, place or person. Times are container claims, corrected only where a "
    "calibration exists. Overlap is computed from nominal times; a window marked uncertain involves a "
    "calibration with non-zero uncertainty. Files with unknown length or time are listed separately and "
    "are not used."
)


class CorrelationService:

    @staticmethod
    def get_correlation(
        case_id: str,
        groups: Optional[str] = None,
        min_overlap_seconds: float = 0.0,
        min_groups: int = 2,
        limit: int = 100,
        offset: int = 0,
    ):
        case_obj = CaseRepository.get_by_id(case_id)
        if not case_obj:
            raise HTTPException(status_code=404, detail="Case not found")

        groups_set = None
        if groups is not None:
            parts = groups.split(",")
            parsed = set()
            for p in parts:
                stripped = p.strip()
                if not stripped:
                    raise HTTPException(status_code=400, detail="Invalid groups")
                parsed.add(stripped)
            groups_set = parsed

        collected = GapService.collect_intervals(case_id, groups_set)
        intervals_by_group = collected["intervals_by_group"]
        unknown_length = collected["unknown_length"]
        unplaced = collected["unplaced"]
        is_truncated = collected["truncated"]

        raw_windows = compute_windows(intervals_by_group, min_groups)

        included_windows = []
        for w in raw_windows:
            if w["length_seconds"] >= min_overlap_seconds and w["length_seconds"] > 0:
                start_str = format_timestamp(w["start"])
                end_str = format_timestamp(w["end"])
                win_id = make_window_id(w["groups"], start_str)
                included_windows.append({
                    "window_id": win_id,
                    "start": start_str,
                    "end": end_str,
                    "length_seconds": float(w["length_seconds"]),
                    "groups": w["groups"],
                    "group_count": w["group_count"],
                    "members": w["members"],
                    "uncertain": w["uncertain"],
                    "_start_dt": w["start"],
                    "_groups_tuple": tuple(w["groups"]),
                })

        included_windows.sort(key=lambda x: (x["_start_dt"], x["_groups_tuple"], x["window_id"]))
        for w in included_windows:
            del w["_start_dt"]
            del w["_groups_tuple"]

        groups_summary = []
        for grp_label in sorted(intervals_by_group.keys()):
            count = len(intervals_by_group[grp_label])
            if count > 0:
                groups_summary.append({
                    "group_label": grp_label,
                    "interval_count": count,
                })

        window_count = len(included_windows)
        if window_count > 0:
            total_overlap_seconds = round(sum(w["length_seconds"] for w in included_windows), 6)
            longest_overlap_seconds = max(w["length_seconds"] for w in included_windows)
            max_simultaneous_groups = max(w["group_count"] for w in included_windows)
        else:
            total_overlap_seconds = 0.0
            longest_overlap_seconds = 0.0
            max_simultaneous_groups = 0

        summary = {
            "window_count": window_count,
            "total_overlap_seconds": total_overlap_seconds,
            "longest_overlap_seconds": longest_overlap_seconds,
            "max_simultaneous_groups": max_simultaneous_groups,
            "truncated": is_truncated,
        }

        paged_windows = included_windows[offset : offset + limit]
        page = {
            "limit": limit,
            "offset": offset,
            "total": window_count,
        }

        return {
            "case_id": case_id,
            "disclaimer": DISCLAIMER,
            "groups": groups_summary,
            "windows": paged_windows,
            "unknown_length": unknown_length,
            "unplaced": unplaced,
            "summary": summary,
            "page": page,
        }
