import datetime
import hashlib
from app.forensic.correlation import merge_ranges, make_window_id, compute_windows
from app.services.gap_service import GapService


def dt(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_01_merge_ranges_empty_and_one():
    assert merge_ranges([]) == []
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:30:00Z")
    assert merge_ranges([(t0, t1)]) == [(t0, t1)]


def test_02_merge_ranges_overlapping():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:15:00Z")
    t2 = dt("2025-06-01T10:30:00Z")
    t3 = dt("2025-06-01T10:45:00Z")
    assert merge_ranges([(t0, t2), (t1, t3)]) == [(t0, t3)]


def test_03_merge_ranges_touching_merges():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:30:00Z")
    t2 = dt("2025-06-01T11:00:00Z")
    assert merge_ranges([(t0, t1), (t1, t2)]) == [(t0, t2)]


def test_04_merge_ranges_disjoint():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:10:00Z")
    t2 = dt("2025-06-01T10:20:00Z")
    t3 = dt("2025-06-01T10:30:00Z")
    assert merge_ranges([(t0, t1), (t2, t3)]) == [(t0, t1), (t2, t3)]


def test_05_merge_ranges_unsorted_input():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:10:00Z")
    t2 = dt("2025-06-01T10:20:00Z")
    t3 = dt("2025-06-01T10:30:00Z")
    assert merge_ranges([(t2, t3), (t0, t1)]) == [(t0, t1), (t2, t3)]


def test_06_merge_ranges_zero_length_ignored():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:10:00Z")
    t2 = dt("2025-06-01T10:20:00Z")
    assert merge_ranges([(t0, t0), (t1, t2), (t2, t2)]) == [(t1, t2)]


def test_07_merge_ranges_contained_range():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:10:00Z")
    t2 = dt("2025-06-01T10:20:00Z")
    t3 = dt("2025-06-01T10:30:00Z")
    assert merge_ranges([(t0, t3), (t1, t2)]) == [(t0, t3)]


def test_08_compute_windows_empty_dict():
    assert compute_windows({}, min_groups=2) == []


def test_09_compute_windows_single_group_never_correlates():
    t0 = dt("2025-06-01T10:00:00Z")
    invs = {
        "CamA": [
            {"evidence_id": "e1", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 600.0},
            {"evidence_id": "e2", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 1200.0},
        ]
    }
    assert compute_windows(invs, min_groups=2) == []


def test_10_compute_windows_two_groups_overlap():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:20:00Z")
    invs = {
        "CamA": [{"evidence_id": "e1", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 1800.0}],
        "CamB": [{"evidence_id": "e2", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 1800.0}],
    }
    wins = compute_windows(invs, min_groups=2)
    assert len(wins) == 1
    w = wins[0]
    assert w["start"] == dt("2025-06-01T10:20:00Z")
    assert w["end"] == dt("2025-06-01T10:30:00Z")
    assert w["length_seconds"] == 600.0
    assert w["groups"] == ["CamA", "CamB"]
    assert w["group_count"] == 2
    assert w["uncertain"] is False


def test_11_compute_windows_touching_groups_no_overlap():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:20:00Z")
    invs = {
        "CamA": [{"evidence_id": "e1", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 1200.0}],
        "CamB": [{"evidence_id": "e2", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 600.0}],
    }
    assert compute_windows(invs, min_groups=2) == []


def test_12_compute_windows_three_group_split():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:10:00Z")
    t2 = dt("2025-06-01T10:20:00Z")
    invs = {
        "CamA": [{"evidence_id": "e1", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 3600.0}],
        "CamB": [{"evidence_id": "e2", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 1800.0}],
        "CamC": [{"evidence_id": "e3", "start": t2, "start_earliest": t2, "start_latest": t2, "duration_seconds": 600.0}],
    }
    wins = compute_windows(invs, min_groups=2)
    assert len(wins) == 3
    assert [(w["start"], w["end"], w["groups"], w["group_count"]) for w in wins] == [
        (dt("2025-06-01T10:10:00Z"), dt("2025-06-01T10:20:00Z"), ["CamA", "CamB"], 2),
        (dt("2025-06-01T10:20:00Z"), dt("2025-06-01T10:30:00Z"), ["CamA", "CamB", "CamC"], 3),
        (dt("2025-06-01T10:30:00Z"), dt("2025-06-01T10:40:00Z"), ["CamA", "CamB"], 2),
    ]


def test_13_compute_windows_min_groups_3():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:10:00Z")
    t2 = dt("2025-06-01T10:20:00Z")
    invs = {
        "CamA": [{"evidence_id": "e1", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 3600.0}],
        "CamB": [{"evidence_id": "e2", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 1800.0}],
        "CamC": [{"evidence_id": "e3", "start": t2, "start_earliest": t2, "start_latest": t2, "duration_seconds": 600.0}],
    }
    wins = compute_windows(invs, min_groups=3)
    assert len(wins) == 1
    assert wins[0]["groups"] == ["CamA", "CamB", "CamC"]
    assert wins[0]["length_seconds"] == 600.0


def test_14_compute_windows_identical_set_adjacent_merge():
    # Group A: [10:00, 10:20], [10:20, 10:40]
    # Group B: [10:00, 10:40]
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:20:00Z")
    invs = {
        "CamA": [
            {"evidence_id": "e1", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 1200.0},
            {"evidence_id": "e2", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 1200.0},
        ],
        "CamB": [
            {"evidence_id": "e3", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 2400.0},
        ]
    }
    wins = compute_windows(invs, min_groups=2)
    assert len(wins) == 1
    assert wins[0]["start"] == t0
    assert wins[0]["end"] == dt("2025-06-01T10:40:00Z")
    assert wins[0]["length_seconds"] == 2400.0


def test_15_compute_windows_members_sorted_and_positive_intersection():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:10:00Z")
    t2 = dt("2025-06-01T10:20:00Z")
    invs = {
        "CamA": [
            {"evidence_id": "e1", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 600.0},
            {"evidence_id": "e2", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 600.0},
        ],
        "CamB": [
            {"evidence_id": "e3", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 1800.0},
        ]
    }
    wins = compute_windows(invs, min_groups=2)
    assert len(wins) == 1
    w = wins[0]
    # Members should be sorted by group_label, and each evidence_ids sorted
    assert [m["group_label"] for m in w["members"]] == ["CamA", "CamB"]
    assert w["members"][0]["evidence_ids"] == ["e1", "e2"]
    assert w["members"][1]["evidence_ids"] == ["e3"]


def test_16_compute_windows_uncertain_flag_true_and_false():
    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T10:10:00Z")
    t_early = dt("2025-06-01T09:59:30Z")
    t_late = dt("2025-06-01T10:00:30Z")
    # Uncertain True:
    invs_unc = {
        "CamA": [{"evidence_id": "e1", "start": t0, "start_earliest": t_early, "start_latest": t_late, "duration_seconds": 1200.0}],
        "CamB": [{"evidence_id": "e2", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 1200.0}],
    }
    assert compute_windows(invs_unc, min_groups=2)[0]["uncertain"] is True

    # Uncertain False:
    invs_cert = {
        "CamA": [{"evidence_id": "e1", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 1200.0}],
        "CamB": [{"evidence_id": "e2", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 1200.0}],
    }
    assert compute_windows(invs_cert, min_groups=2)[0]["uncertain"] is False


def test_17_compute_windows_zero_duration_interval_ignored():
    t0 = dt("2025-06-01T10:00:00Z")
    invs = {
        "CamA": [{"evidence_id": "e1", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 0.0}],
        "CamB": [{"evidence_id": "e2", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 600.0}],
    }
    assert compute_windows(invs, min_groups=2) == []


def test_18_make_window_id_formula():
    groups = ["CamA", "CamB"]
    start_str = "2025-06-01T10:20:00Z"
    exp = hashlib.sha256(b"OVERLAP|CamA|CamB|2025-06-01T10:20:00Z").hexdigest()[:16]
    assert make_window_id(groups, start_str) == exp


def test_19_correlation_source_no_prohibited_imports_or_open():
    import ast
    with open("app/forensic/correlation.py", "r", encoding="utf-8") as f:
        src = f.read()

    assert "open(" not in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in ("sqlite3", "os", "pathlib")
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in ("sqlite3", "os", "pathlib")


def test_20_groups_invalid_query_returns_400(client):
    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]
    r = client.get(f"/api/cases/{cid}/correlation?groups=%20,%20")
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid groups"


def test_21_collect_intervals_keys_and_groups_set(client):
    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]
    e1 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "1.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    client.put(f"/api/evidence/{e1}/group", json={"group_label": "Grp1"})

    res = GapService.collect_intervals(cid, {"Grp1"})
    assert set(res.keys()) == {"intervals_by_group", "unknown_length", "unplaced", "truncated"}
    assert res["truncated"] is False

    res_empty = GapService.collect_intervals(cid, {"OtherGrp"})
    assert res_empty["unplaced"] == []


def test_22_get_gaps_output_unchanged_after_refactor(client):
    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]
    gaps_res = client.get(f"/api/cases/{cid}/gaps").json()
    assert gaps_res["case_id"] == cid
    assert gaps_res["gaps"] == []
    assert gaps_res["summary"] == {"gap_count": 0, "total_gap_seconds": 0.0, "longest_gap_seconds": 0.0, "truncated": False}
    assert gaps_res["page"] == {"limit": 100, "offset": 0, "total": 0}


def test_adjacent_segments_same_groups_merge():
    # Case 1: CamA 10:00 for 3600s, CamB 10:00 for 3600s, CamC 10:20 for 600s with min_groups=2
    t0 = dt("2025-06-01T10:00:00Z")
    t_c = dt("2025-06-01T10:20:00Z")
    invs = {
        "CamA": [{"evidence_id": "eA", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 3600.0}],
        "CamB": [{"evidence_id": "eB", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 3600.0}],
        "CamC": [{"evidence_id": "eC", "start": t_c, "start_earliest": t_c, "start_latest": t_c, "duration_seconds": 600.0}],
    }
    wins = compute_windows(invs, min_groups=2)
    assert len(wins) == 3
    assert wins[0]["groups"] == ["CamA", "CamB"]
    assert wins[0]["start"] == dt("2025-06-01T10:00:00Z")
    assert wins[0]["end"] == dt("2025-06-01T10:20:00Z")
    assert wins[1]["groups"] == ["CamA", "CamB", "CamC"]
    assert wins[1]["start"] == dt("2025-06-01T10:20:00Z")
    assert wins[1]["end"] == dt("2025-06-01T10:30:00Z")
    assert wins[2]["groups"] == ["CamA", "CamB"]
    assert wins[2]["start"] == dt("2025-06-01T10:30:00Z")
    assert wins[2]["end"] == dt("2025-06-01T11:00:00Z")

    # Case 2: CamA 10:00 3600s, CamB 10:00 3600s, CamC 12:00 for 60s with min_groups=2
    t_c2 = dt("2025-06-01T12:00:00Z")
    invs2 = {
        "CamA": [{"evidence_id": "eA", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 3600.0}],
        "CamB": [{"evidence_id": "eB", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 3600.0}],
        "CamC": [{"evidence_id": "eC", "start": t_c2, "start_earliest": t_c2, "start_latest": t_c2, "duration_seconds": 60.0}],
    }
    wins2 = compute_windows(invs2, min_groups=2)
    assert len(wins2) == 1
    assert wins2[0]["groups"] == ["CamA", "CamB"]
    assert wins2[0]["start"] == t0
    assert wins2[0]["end"] == dt("2025-06-01T11:00:00Z")


def test_windows_members_sorted_by_group_label():
    t0 = dt("2025-06-01T10:00:00Z")
    # Insert in reverse alphabetical order: CamZ, CamM, CamA
    invs = {
        "CamZ": [{"evidence_id": "eZ", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 1800.0}],
        "CamM": [{"evidence_id": "eM", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 1800.0}],
        "CamA": [{"evidence_id": "eA", "start": t0, "start_earliest": t0, "start_latest": t0, "duration_seconds": 1800.0}],
    }
    wins = compute_windows(invs, min_groups=2)
    assert len(wins) == 1
    labels = [m["group_label"] for m in wins[0]["members"]]
    assert labels == ["CamA", "CamM", "CamZ"]


def test_service_sorts_windows(client, monkeypatch):
    import app.services.correlation_service as cs_mod

    t0 = dt("2025-06-01T10:00:00Z")
    t1 = dt("2025-06-01T11:00:00Z")
    t2 = dt("2025-06-01T12:00:00Z")

    win_late = {
        "start": t1,
        "end": t2,
        "length_seconds": 3600.0,
        "groups": ["CamA", "CamB"],
        "group_count": 2,
        "members": [{"group_label": "CamA", "evidence_ids": ["e1"]}, {"group_label": "CamB", "evidence_ids": ["e2"]}],
        "uncertain": False,
    }
    win_early = {
        "start": t0,
        "end": t1,
        "length_seconds": 3600.0,
        "groups": ["CamA", "CamB"],
        "group_count": 2,
        "members": [{"group_label": "CamA", "evidence_ids": ["e1"]}, {"group_label": "CamB", "evidence_ids": ["e2"]}],
        "uncertain": False,
    }

    monkeypatch.setattr(cs_mod, "compute_windows", lambda invs, min_g: [win_late, win_early])

    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]

    res = client.get(f"/api/cases/{cid}/correlation")
    assert res.status_code == 200
    data = res.json()
    assert len(data["windows"]) == 2
    assert data["windows"][0]["start"] == "2025-06-01T10:00:00Z"
    assert data["windows"][1]["start"] == "2025-06-01T11:00:00Z"

