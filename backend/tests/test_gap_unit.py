import ast
import datetime
import hashlib
import math
from unittest.mock import patch
import pytest

from app.forensic.gap_analysis import (
    MAX_DURATION_SECONDS,
    validate_duration,
    compute_gaps,
    make_gap_id,
)
from app.repositories.metadata_repository import MetadataRepository
from app.repositories.gap_repository import GapRepository


def T(hms, day="2025-06-01"):
    return f"{day}T{hms}Z"


def test_01_constants_and_module_api():
    assert MAX_DURATION_SECONDS == 315360000
    assert callable(validate_duration)
    assert callable(compute_gaps)
    assert callable(make_gap_id)


def test_02_validate_duration_none_and_absent():
    val, reason = validate_duration(None)
    assert val is None and reason == "NO_DURATION"


def test_03_validate_duration_valid_numeric():
    assert validate_duration(0) == (0.0, None)
    assert validate_duration(100) == (100.0, None)
    assert validate_duration(12.345) == (12.345, None)
    assert validate_duration(MAX_DURATION_SECONDS) == (float(MAX_DURATION_SECONDS), None)


def test_04_validate_duration_out_of_range():
    assert validate_duration(MAX_DURATION_SECONDS + 1) == (None, "INVALID_DURATION")
    assert validate_duration(-1) == (None, "INVALID_DURATION")
    assert validate_duration(-0.0001) == (None, "INVALID_DURATION")


def test_05_validate_duration_invalid_types_and_specials():
    assert validate_duration(True) == (None, "INVALID_DURATION")
    assert validate_duration(False) == (None, "INVALID_DURATION")
    assert validate_duration("100") == (None, "INVALID_DURATION")
    assert validate_duration(float("nan")) == (None, "INVALID_DURATION")
    assert validate_duration(float("inf")) == (None, "INVALID_DURATION")
    assert validate_duration(float("-inf")) == (None, "INVALID_DURATION")
    assert validate_duration([10]) == (None, "INVALID_DURATION")
    assert validate_duration({"a": 1}) == (None, "INVALID_DURATION")


def test_06_compute_gaps_empty_and_single():
    assert compute_gaps([]) == []
    single = [{
        "evidence_id": "e1",
        "start": datetime.datetime(2025, 6, 1, 10, 0, 0, tzinfo=datetime.timezone.utc),
        "start_earliest": datetime.datetime(2025, 6, 1, 10, 0, 0, tzinfo=datetime.timezone.utc),
        "start_latest": datetime.datetime(2025, 6, 1, 10, 0, 0, tzinfo=datetime.timezone.utc),
        "duration_seconds": 60.0,
    }]
    assert compute_gaps(single) == []


def test_07_compute_gaps_touching_and_overlapping():
    t1 = datetime.datetime(2025, 6, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    t2 = datetime.datetime(2025, 6, 1, 10, 10, 0, tzinfo=datetime.timezone.utc)
    # Touching: int1 ends at 10:10:00, int2 starts at 10:10:00
    touching = [
        {"evidence_id": "e1", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 600.0},
        {"evidence_id": "e2", "start": t2, "start_earliest": t2, "start_latest": t2, "duration_seconds": 600.0},
    ]
    assert compute_gaps(touching) == []

    # Overlapping: int1 ends at 10:15:00, int2 starts at 10:10:00
    overlapping = [
        {"evidence_id": "e1", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 900.0},
        {"evidence_id": "e2", "start": t2, "start_earliest": t2, "start_latest": t2, "duration_seconds": 600.0},
    ]
    assert compute_gaps(overlapping) == []


def test_08_compute_gaps_running_max_long_first_file():
    t1 = datetime.datetime(2025, 6, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    t2 = datetime.datetime(2025, 6, 1, 10, 15, 0, tzinfo=datetime.timezone.utc)
    t3 = datetime.datetime(2025, 6, 1, 11, 30, 0, tzinfo=datetime.timezone.utc)
    intervals = [
        {"evidence_id": "e1", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 3600.0},  # ends 11:00:00
        {"evidence_id": "e2", "start": t2, "start_earliest": t2, "start_latest": t2, "duration_seconds": 600.0},   # ends 10:25:00
        {"evidence_id": "e3", "start": t3, "start_earliest": t3, "start_latest": t3, "duration_seconds": 600.0},   # starts 11:30:00
    ]
    gaps = compute_gaps(intervals)
    assert len(gaps) == 1
    g = gaps[0]
    assert g["before_evidence_id"] == "e1"
    assert g["after_evidence_id"] == "e3"
    assert g["start"] == datetime.datetime(2025, 6, 1, 11, 0, 0, tzinfo=datetime.timezone.utc)
    assert g["end"] == datetime.datetime(2025, 6, 1, 11, 30, 0, tzinfo=datetime.timezone.utc)
    assert g["length_seconds"] == 1800.0


def test_09_compute_gaps_tie_on_end_keeps_first():
    t1 = datetime.datetime(2025, 6, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    t2 = datetime.datetime(2025, 6, 1, 10, 5, 0, tzinfo=datetime.timezone.utc)
    t3 = datetime.datetime(2025, 6, 1, 10, 20, 0, tzinfo=datetime.timezone.utc)
    intervals = [
        {"evidence_id": "eA", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 600.0},  # ends 10:10:00
        {"evidence_id": "eB", "start": t2, "start_earliest": t2, "start_latest": t2, "duration_seconds": 300.0},  # ends 10:10:00 (tie)
        {"evidence_id": "eC", "start": t3, "start_earliest": t3, "start_latest": t3, "duration_seconds": 600.0},  # starts 10:20:00
    ]
    gaps = compute_gaps(intervals)
    assert len(gaps) == 1
    # On tie on end, ref must NOT be updated; it must keep the FIRST one ("eA")
    assert gaps[0]["before_evidence_id"] == "eA"
    assert gaps[0]["after_evidence_id"] == "eC"


def test_10_compute_gaps_unsorted_input():
    t1 = datetime.datetime(2025, 6, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    t2 = datetime.datetime(2025, 6, 1, 10, 30, 0, tzinfo=datetime.timezone.utc)
    intervals = [
        {"evidence_id": "e2", "start": t2, "start_earliest": t2, "start_latest": t2, "duration_seconds": 600.0},
        {"evidence_id": "e1", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 600.0},
    ]
    gaps = compute_gaps(intervals)
    assert len(gaps) == 1
    assert gaps[0]["before_evidence_id"] == "e1"
    assert gaps[0]["after_evidence_id"] == "e2"


def test_11_compute_gaps_zero_duration():
    t1 = datetime.datetime(2025, 6, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    t2 = datetime.datetime(2025, 6, 1, 10, 10, 0, tzinfo=datetime.timezone.utc)
    intervals = [
        {"evidence_id": "e1", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 0.0},
        {"evidence_id": "e2", "start": t2, "start_earliest": t2, "start_latest": t2, "duration_seconds": 0.0},
    ]
    gaps = compute_gaps(intervals)
    assert len(gaps) == 1
    assert gaps[0]["length_seconds"] == 600.0
    assert gaps[0]["start"] == t1
    assert gaps[0]["end"] == t2


def test_12_compute_gaps_min_clamp_to_zero_and_certainty():
    t1 = datetime.datetime(2025, 6, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    # int1: duration 60s, latest end = 10:01:00 + 100s = 10:02:40
    # int2: nominal start = 10:02:00, earliest start = 10:01:00
    # nominal gap = 10:02:00 - 10:01:00 = 60s > 0
    # unrounded min = 10:01:00 - 10:02:40 = -100s <= 0 -> clamped to 0.0, UNCERTAIN
    int1 = {
        "evidence_id": "e1",
        "start": t1,
        "start_earliest": t1,
        "start_latest": t1 + datetime.timedelta(seconds=100),
        "duration_seconds": 60.0,
    }
    int2 = {
        "evidence_id": "e2",
        "start": t1 + datetime.timedelta(seconds=120),
        "start_earliest": t1 + datetime.timedelta(seconds=60),
        "start_latest": t1 + datetime.timedelta(seconds=180),
        "duration_seconds": 60.0,
    }
    gaps = compute_gaps([int1, int2])
    assert len(gaps) == 1
    g = gaps[0]
    assert g["length_seconds"] == 60.0
    assert g["length_min_seconds"] == 0.0
    assert g["certainty"] == "UNCERTAIN"


def test_13_compute_gaps_fractional_seconds():
    t1 = datetime.datetime(2025, 6, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    t2 = datetime.datetime(2025, 6, 1, 10, 0, 1, 123456, tzinfo=datetime.timezone.utc)
    intervals = [
        {"evidence_id": "e1", "start": t1, "start_earliest": t1, "start_latest": t1, "duration_seconds": 0.5},
        {"evidence_id": "e2", "start": t2, "start_earliest": t2, "start_latest": t2, "duration_seconds": 1.0},
    ]
    gaps = compute_gaps(intervals)
    assert len(gaps) == 1
    g = gaps[0]
    assert g["length_seconds"] == 0.623456
    assert g["length_min_seconds"] == 0.623456
    assert g["length_max_seconds"] == 0.623456
    assert g["certainty"] == "CERTAIN"


def test_14_make_gap_id_formula():
    expected = hashlib.sha256(b"GAP|CamA|ev1|ev2").hexdigest()[:16]
    computed = make_gap_id("CamA", "ev1", "ev2")
    assert computed == expected
    assert len(computed) == 16
    assert computed == computed.lower()


def test_15_pure_module_gap_analysis_no_io_imports():
    with open("app/forensic/gap_analysis.py", "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in ("sqlite3", "os", "pathlib"), f"Forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in ("sqlite3", "os", "pathlib"), f"Forbidden import from: {node.module}"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id != "open", "Forbidden open() call in gap_analysis.py"


def test_16_service_runtime_error_gives_500_generic_and_audits_internal_error(client):
    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]
    r_ev = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f.bin", "evidence_type": "BIN", "file_size": 1})
    eid = r_ev.json()["evidence_id"]

    with patch.object(GapRepository, "set_evidence_group", side_effect=RuntimeError("TOP_SECRET_DB_CORRUPTION")):
        res = client.put(f"/api/evidence/{eid}/group", json={"group_label": "CamA"})
        assert res.status_code == 500
        assert res.json() == {"detail": "Internal error while saving group"}
        assert "TOP_SECRET_DB_CORRUPTION" not in res.text

    audit = client.get(f"/api/audit-log?evidence_id={eid}").json()
    errors = [a for a in audit if a["action"] == "GROUP_SET" and a["outcome"] == "ERROR"]
    assert len(errors) == 1
    assert errors[0]["http_status"] == 500
    assert errors[0]["details"]["reason"] == "INTERNAL_ERROR"
    assert "TOP_SECRET_DB_CORRUPTION" not in str(errors[0])


def test_17_corrupt_metadata_json_and_non_dict_and_fields_not_list(client):
    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]

    # Evidence 1: corrupt JSON string in result
    e1 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "1.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    MetadataRepository.upsert("EVIDENCE", e1, cid, "MP4", "1", "OK", "INVALID_NOT_JSON{", "2026-01-01T00:00:00Z")

    # Evidence 2: result is valid JSON but primitive integer
    e2 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "2.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    MetadataRepository.upsert("EVIDENCE", e2, cid, "MP4", "1", "OK", 12345, "2026-01-01T00:00:00Z")

    # Evidence 3: result is valid dict but 'fields' is not a list
    e3 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "3.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    MetadataRepository.upsert("EVIDENCE", e3, cid, "MP4", "1", "OK", {"fields": "not-a-list"}, "2026-01-01T00:00:00Z")

    # Evidence 4: 'fields' is a list with non-dict items
    e4 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "4.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    MetadataRepository.upsert("EVIDENCE", e4, cid, "MP4", "1", "OK", {"fields": ["string_elem", 123]}, "2026-01-01T00:00:00Z")

    res = client.get(f"/api/cases/{cid}/gaps")
    assert res.status_code == 200
    data = res.json()
    unplaced_ids = {u["evidence_id"] for u in data["unplaced"]}
    assert e1 in unplaced_ids
    assert e2 in unplaced_ids
    assert e3 in unplaced_ids
    assert e4 in unplaced_ids


def test_18_unknown_length_with_invalid_metadata_field(client):
    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]
    eid = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    meta = {
        "fields": [
            {"field": "creation_time", "interpreted_value": "2025-06-01T10:00:00Z"},
            {"field": "duration", "interpreted_value": "NOT_A_NUMBER"},
        ]
    }
    MetadataRepository.upsert("EVIDENCE", eid, cid, "MP4", "1", "OK", meta, "2026-01-01T00:00:00Z")
    res = client.get(f"/api/cases/{cid}/gaps")
    assert res.status_code == 200
    data = res.json()
    assert len(data["unknown_length"]) == 1
    u = data["unknown_length"][0]
    assert u["evidence_id"] == eid
    assert u["reason"] == "INVALID_DURATION"
    assert u["start"] == "2025-06-01T10:00:00Z"


def test_19_overflow_error_results_in_time_out_of_range(client):
    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]
    eid = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    meta = {
        "fields": [
            {"field": "creation_time", "interpreted_value": "9999-12-31T23:59:59Z"},
            {"field": "duration", "interpreted_value": 315360000},
        ]
    }
    MetadataRepository.upsert("EVIDENCE", eid, cid, "MP4", "1", "OK", meta, "2026-01-01T00:00:00Z")
    res = client.get(f"/api/cases/{cid}/gaps")
    assert res.status_code == 200
    data = res.json()
    assert len(data["unknown_length"]) == 1
    assert data["unknown_length"][0]["evidence_id"] == eid
    assert data["unknown_length"][0]["reason"] == "TIME_OUT_OF_RANGE"


def test_20_groups_list_excludes_groups_without_intervals(client):
    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]
    eid = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    # Evidence has group 'GhostGroup' but no creation_time, so it becomes unplaced
    client.put(f"/api/evidence/{eid}/group", json={"group_label": "GhostGroup"})
    res = client.get(f"/api/cases/{cid}/gaps")
    assert res.status_code == 200
    data = res.json()
    # GhostGroup has 0 intervals, so it MUST NOT appear in groups list
    assert data["groups"] == []
    assert len(data["unplaced"]) == 1
    assert data["unplaced"][0]["group_label"] == "GhostGroup"


def test_21_gap_candidate_min_gap_boundary(client):
    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]
    e1 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "1.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    e2 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "2.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    meta1 = {"fields": [{"field": "creation_time", "interpreted_value": "2025-06-01T10:00:00Z"}, {"field": "duration", "interpreted_value": 60}]}
    meta2 = {"fields": [{"field": "creation_time", "interpreted_value": "2025-06-01T10:02:00Z"}, {"field": "duration", "interpreted_value": 60}]}
    MetadataRepository.upsert("EVIDENCE", e1, cid, "MP4", "1", "OK", meta1, "2026-01-01T00:00:00Z")
    MetadataRepository.upsert("EVIDENCE", e2, cid, "MP4", "1", "OK", meta2, "2026-01-01T00:00:00Z")

    # Gap length is 60.0s
    res_at_60 = client.get(f"/api/cases/{cid}/gaps?min_gap_seconds=60.0").json()
    assert len(res_at_60["gaps"]) == 1
    res_above_60 = client.get(f"/api/cases/{cid}/gaps?min_gap_seconds=60.000001").json()
    assert len(res_above_60["gaps"]) == 0


def test_22_sorting_uses_datetime_not_string():
    tA = datetime.datetime.fromisoformat("2025-06-01T11:00:00+01:00")
    tB = datetime.datetime.fromisoformat("2025-06-01T10:30:00+00:00")
    assert str(tA) > str(tB)
    assert tA < tB
    intervals = [
        {"evidence_id": "eB", "start": tB, "start_earliest": tB, "start_latest": tB, "duration_seconds": 60.0},
        {"evidence_id": "eA", "start": tA, "start_earliest": tA, "start_latest": tA, "duration_seconds": 60.0},
    ]
    gaps = compute_gaps(intervals)
    assert len(gaps) == 1
    assert gaps[0]["before_evidence_id"] == "eA"
    assert gaps[0]["after_evidence_id"] == "eB"


def test_23_calibration_truncated_passthrough(client):
    from app.services.calibration_service import CalibrationService
    r_case = client.post("/api/cases", json={"case_name": "C"})
    cid = r_case.json()["case_id"]
    with patch.object(CalibrationService, "get_calibrated_times", return_value={"items": [], "summary": {"truncated": True}}):
        res = client.get(f"/api/cases/{cid}/gaps")
        assert res.status_code == 200
        assert res.json()["summary"]["truncated"] is True


def test_24_case_isolation_empty_case_not_polluted_by_other_cases(client):
    c1 = client.post("/api/cases", json={"case_name": "C1"}).json()["case_id"]
    client.post(f"/api/cases/{c1}/evidence", json={"original_filename": "f.bin", "evidence_type": "BIN", "file_size": 1})
    c2 = client.post("/api/cases", json={"case_name": "C2"}).json()["case_id"]

    ids = GapRepository.get_case_evidence_ids(c2, 100)
    assert ids == []

    data = client.get(f"/api/cases/{c2}/gaps").json()
    assert data["unplaced"] == []
    assert data["gaps"] == []
    assert data["unknown_length"] == []


def test_metadata_query_is_case_restricted():
    from app.repositories.gap_repository import GapRepository as R
    from app.repositories.metadata_repository import MetadataRepository as M
    M.upsert("EVIDENCE", "e1", "caseA", "MP4", "1", "OK", {"fields": []}, "2026-01-01T00:00:00Z")
    M.upsert("EVIDENCE", "e2", "caseB", "MP4", "1", "OK", {"fields": []}, "2026-01-01T00:00:00Z")
    rows = R.get_case_metadata_extractions("caseA", 10)
    assert [r["subject_id"] for r in rows] == ["e1"]


