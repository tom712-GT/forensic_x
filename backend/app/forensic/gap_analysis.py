import hashlib
import math
import datetime

MAX_DURATION_SECONDS = 315360000


def validate_duration(value) -> tuple[float | None, str | None]:
    if value is None:
        return None, "NO_DURATION"
    if isinstance(value, bool):
        return None, "INVALID_DURATION"
    if not isinstance(value, (int, float)):
        return None, "INVALID_DURATION"
    if math.isnan(value) or math.isinf(value):
        return None, "INVALID_DURATION"
    if value < 0 or value > MAX_DURATION_SECONDS:
        return None, "INVALID_DURATION"
    return float(value), None


def make_gap_id(group_label: str, before_id: str, after_id: str) -> str:
    raw = f"GAP|{group_label}|{before_id}|{after_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def compute_gaps(intervals: list[dict]) -> list[dict]:
    if not intervals:
        return []

    sorted_intervals = sorted(intervals, key=lambda x: (x["start"], x["evidence_id"]))

    gaps = []
    ref = sorted_intervals[0]
    ref_dur_td = datetime.timedelta(seconds=ref["duration_seconds"])
    ref_end_nominal = ref["start"] + ref_dur_td
    ref_end_earliest = ref["start_earliest"] + ref_dur_td
    ref_end_latest = ref["start_latest"] + ref_dur_td

    for N in sorted_intervals[1:]:
        N_start_nominal = N["start"]
        N_start_earliest = N["start_earliest"]
        N_start_latest = N["start_latest"]
        N_dur_td = datetime.timedelta(seconds=N["duration_seconds"])
        N_end_nominal = N_start_nominal + N_dur_td
        N_end_earliest = N_start_earliest + N_dur_td
        N_end_latest = N_start_latest + N_dur_td

        nominal_len = (N_start_nominal - ref_end_nominal).total_seconds()
        if nominal_len > 0:
            unrounded_min = (N_start_earliest - ref_end_latest).total_seconds()
            length_min_seconds = max(0.0, unrounded_min)
            length_max_seconds = (N_start_latest - ref_end_earliest).total_seconds()
            certainty = "CERTAIN" if unrounded_min > 0 else "UNCERTAIN"

            gaps.append({
                "start": ref_end_nominal,
                "end": N_start_nominal,
                "length_seconds": round(nominal_len, 6),
                "length_min_seconds": round(length_min_seconds, 6),
                "length_max_seconds": round(length_max_seconds, 6),
                "certainty": certainty,
                "before_evidence_id": ref["evidence_id"],
                "after_evidence_id": N["evidence_id"]
            })

        if N_end_nominal > ref_end_nominal:
            ref = N
            ref_end_nominal = N_end_nominal
            ref_end_earliest = N_end_earliest
            ref_end_latest = N_end_latest

    return gaps
