import hashlib
import datetime


def merge_ranges(
    ranges: list[tuple[datetime.datetime, datetime.datetime]],
) -> list[tuple[datetime.datetime, datetime.datetime]]:
    positive_ranges = [r for r in ranges if r[1] > r[0]]
    if not positive_ranges:
        return []

    sorted_ranges = sorted(positive_ranges, key=lambda r: (r[0], r[1]))
    merged = [sorted_ranges[0]]

    for current in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        if current[0] <= last_end:
            if current[1] > last_end:
                merged[-1] = (last_start, current[1])
        else:
            merged.append(current)

    return merged


def make_window_id(groups: list[str], start_str: str) -> str:
    raw = "OVERLAP|" + "|".join(groups) + "|" + start_str
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def compute_windows(
    intervals_by_group: dict[str, list[dict]],
    min_groups: int,
) -> list[dict]:
    # 1. Compute union of positive ranges per group
    group_unions = {}
    for grp, invs in intervals_by_group.items():
        ranges = []
        for inv in invs:
            s = inv["start"]
            dur = inv.get("duration_seconds", 0.0)
            if dur > 0:
                e = s + datetime.timedelta(seconds=dur)
                if e > s:
                    ranges.append((s, e))
        merged = merge_ranges(ranges)
        if merged:
            group_unions[grp] = merged

    if not group_unions or len(group_unions) < min_groups:
        return []

    # 2. Collect all boundary datetimes across all group unions
    boundaries = set()
    for ranges in group_unions.values():
        for s, e in ranges:
            boundaries.add(s)
            boundaries.add(e)

    sorted_boundaries = sorted(boundaries)
    if len(sorted_boundaries) < 2:
        return []

    # 3. For each consecutive boundary pair, find active groups
    segments = []
    for i in range(len(sorted_boundaries) - 1):
        a = sorted_boundaries[i]
        b = sorted_boundaries[i + 1]
        if b <= a:
            continue

        active = []
        for grp, ranges in group_unions.items():
            for r_start, r_end in ranges:
                if r_start <= a and r_end >= b:
                    active.append(grp)
                    break

        if len(active) >= min_groups:
            segments.append((a, b, sorted(active)))

    if not segments:
        return []

    # 4. Merge adjacent segments with identical active groups
    merged_segments = []
    curr_start, curr_end, curr_groups = segments[0]

    for next_start, next_end, next_groups in segments[1:]:
        if curr_end == next_start and curr_groups == next_groups:
            curr_end = next_end
        else:
            merged_segments.append((curr_start, curr_end, curr_groups))
            curr_start, curr_end, curr_groups = next_start, next_end, next_groups
    merged_segments.append((curr_start, curr_end, curr_groups))

    # 5. Build window dicts
    windows = []
    for win_start, win_end, groups in merged_segments:
        length_sec = round((win_end - win_start).total_seconds(), 6)
        if length_sec <= 0:
            continue

        members = []
        is_uncertain = False

        for grp in intervals_by_group.keys():
            if grp not in groups:
                continue
            matching_ids = []
            for inv in intervals_by_group.get(grp, []):
                inv_start = inv["start"]
                dur = inv.get("duration_seconds", 0.0)
                if dur <= 0:
                    continue
                inv_end = inv_start + datetime.timedelta(seconds=dur)
                if inv_end > inv_start and inv_start < win_end and inv_end > win_start:
                    matching_ids.append(inv["evidence_id"])
                    if inv.get("start_latest") > inv.get("start_earliest"):
                        is_uncertain = True

            members.append({
                "group_label": grp,
                "evidence_ids": sorted(matching_ids),
            })

        members.sort(key=lambda m: m["group_label"])

        windows.append({
            "start": win_start,
            "end": win_end,
            "length_seconds": length_sec,
            "groups": groups,
            "group_count": len(groups),
            "members": members,
            "uncertain": is_uncertain,
        })

    return windows
