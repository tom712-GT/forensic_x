import datetime
import pytest
import sqlite3
from app.forensic.clock_calibration import (
    compute_offset, apply_offset, within_plausible_years,
    MAX_OFFSET_SECONDS, MAX_UNCERTAINTY_SECONDS
)
from app.repositories.calibration_repository import CalibrationRepository
from app.services.calibration_service import CalibrationService
from app.schemas.calibration import CalibrationCreate
from app.db.database import get_connection

def test_compute_offset_positive():
    device = datetime.datetime(2026, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    ref = datetime.datetime(2026, 1, 1, 10, 0, 5, tzinfo=datetime.timezone.utc)
    assert compute_offset(device, ref) == 5.0

def test_compute_offset_negative():
    device = datetime.datetime(2026, 1, 1, 10, 0, 5, tzinfo=datetime.timezone.utc)
    ref = datetime.datetime(2026, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    assert compute_offset(device, ref) == -5.0

def test_compute_offset_zero():
    device = datetime.datetime(2026, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    assert compute_offset(device, device) == 0.0

def test_compute_offset_fractional():
    device = datetime.datetime(2026, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    ref = datetime.datetime(2026, 1, 1, 10, 0, 0, 250000, tzinfo=datetime.timezone.utc)
    assert compute_offset(device, ref) == 0.25

def test_compute_offset_rounding():
    device = datetime.datetime(2026, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    ref = datetime.datetime(2026, 1, 1, 10, 0, 0, 123456, tzinfo=datetime.timezone.utc)
    # The diff is exactly 0.123456
    assert compute_offset(device, ref) == 0.123456

def test_compute_offset_large():
    device = datetime.datetime(1990, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    ref = datetime.datetime(2100, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    assert compute_offset(device, ref) == 3471292800.0

def test_apply_offset_exact():
    dt = datetime.datetime(2026, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    nom, ear, lat = apply_offset(dt, 5.0, 1.0)
    assert nom == datetime.datetime(2026, 1, 1, 10, 0, 5, tzinfo=datetime.timezone.utc)
    assert ear == datetime.datetime(2026, 1, 1, 10, 0, 4, tzinfo=datetime.timezone.utc)
    assert lat == datetime.datetime(2026, 1, 1, 10, 0, 6, tzinfo=datetime.timezone.utc)

def test_apply_offset_zero_uncertainty():
    dt = datetime.datetime(2026, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    nom, ear, lat = apply_offset(dt, 5.0, 0.0)
    assert nom == ear == lat == datetime.datetime(2026, 1, 1, 10, 0, 5, tzinfo=datetime.timezone.utc)

def test_apply_offset_overflow_year_9999():
    dt = datetime.datetime(9999, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc)
    with pytest.raises(OverflowError):
        apply_offset(dt, 10.0, 0.0)

def test_apply_offset_overflow_year_1():
    dt = datetime.datetime(1, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    with pytest.raises(OverflowError):
        apply_offset(dt, -10.0, 0.0)

def test_apply_offset_microseconds():
    dt = datetime.datetime(2026, 1, 1, 10, 0, 0, 500000, tzinfo=datetime.timezone.utc)
    nom, ear, lat = apply_offset(dt, 0.25, 0.1)
    assert nom.microsecond == 750000
    assert ear.microsecond == 650000
    assert lat.microsecond == 850000

def test_within_plausible_years_1989():
    dt = datetime.datetime(1989, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc)
    assert not within_plausible_years(dt, 1990, 2100)

def test_within_plausible_years_1990():
    dt = datetime.datetime(1990, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    assert within_plausible_years(dt, 1990, 2100)

def test_within_plausible_years_2100():
    dt = datetime.datetime(2100, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc)
    assert within_plausible_years(dt, 1990, 2100)

def test_within_plausible_years_2101():
    dt = datetime.datetime(2101, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    assert not within_plausible_years(dt, 1990, 2100)

def test_constants():
    assert MAX_OFFSET_SECONDS == 315360000
    assert MAX_UNCERTAINTY_SECONDS == 31536000

def test_pure_module_imports():
    with open("app/forensic/clock_calibration.py") as f:
        content = f.read()
    assert "sqlite3" not in content
    assert "os" not in content
    assert "pathlib" not in content
    assert "open" not in content

def test_repository_insert_supersede(client):
    r = client.post("/api/cases", json={"case_name": "C"})
    cid = r.json()["case_id"]
    r = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f", "evidence_type": "BIN", "file_size": 1})
    eid = r.json()["evidence_id"]
    
    CalibrationRepository.insert_and_supersede("r1", eid, cid, "dev", "ref", 1.0, 0.0, None, [], "e1", "U")
    with get_connection() as c:
        active = c.execute("SELECT * FROM calibration_references WHERE evidence_id=? AND superseded_at IS NULL", (eid,)).fetchall()
        assert len(active) == 1
        assert active[0]["reference_id"] == "r1"
        
    CalibrationRepository.insert_and_supersede("r2", eid, cid, "dev", "ref", 2.0, 0.0, None, [], "e2", "U")
    with get_connection() as c:
        active = c.execute("SELECT * FROM calibration_references WHERE evidence_id=? AND superseded_at IS NULL", (eid,)).fetchall()
        assert len(active) == 1
        assert active[0]["reference_id"] == "r2"
        old = c.execute("SELECT superseded_at, superseded_by FROM calibration_references WHERE reference_id='r1'").fetchone()
        assert old["superseded_at"] == "e2"
        assert old["superseded_by"] == "r2"

def test_repository_unique_index_violation(client):
    r = client.post("/api/cases", json={"case_name": "C"})
    cid = r.json()["case_id"]
    r = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f", "evidence_type": "BIN", "file_size": 1})
    eid = r.json()["evidence_id"]
    
    with get_connection() as c:
        c.execute("INSERT INTO calibration_references (reference_id, evidence_id, case_id, device_time, reference_time, offset_seconds, uncertainty_seconds, flags, entered_at, entered_by) VALUES (?,?,?,?,?,?,?,?,?,?)", ("rx", eid, cid, "d", "r", 1.0, 0.0, "[]", "e", "u"))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO calibration_references (reference_id, evidence_id, case_id, device_time, reference_time, offset_seconds, uncertainty_seconds, flags, entered_at, entered_by) VALUES (?,?,?,?,?,?,?,?,?,?)", ("ry", eid, cid, "d", "r", 1.0, 0.0, "[]", "e", "u"))

def test_repository_rows_never_deleted():
    with open("app/repositories/calibration_repository.py") as f:
        assert "DELETE" not in f.read().upper()

def test_service_integrity_error_409(client, monkeypatch):
    r = client.post("/api/cases", json={"case_name": "C"})
    cid = r.json()["case_id"]
    r = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f", "evidence_type": "BIN", "file_size": 1})
    eid = r.json()["evidence_id"]
    
    def raise_integrity(*args, **kwargs):
        raise sqlite3.IntegrityError("fake")
    monkeypatch.setattr(CalibrationRepository, "insert_and_supersede", raise_integrity)
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        CalibrationService.set_calibration(eid, CalibrationCreate(device_time="2026-01-01T00:00:00Z", reference_time="2026-01-01T00:00:00Z", uncertainty_seconds=0))
    assert exc.value.status_code == 409
    assert exc.value.detail == "Calibration conflict, retry"
    
    rows = client.get(f"/api/audit-log?evidence_id={eid}&limit=500").json()
    last = [r for r in rows if r["action"] == "CALIBRATION_SET"][-1]
    assert last["action"] == "CALIBRATION_SET"
    assert last["outcome"] == "REJECTED"
    assert last["details"]["reason"] == "CONFLICT"

def test_service_internal_error_500(client, monkeypatch):
    r = client.post("/api/cases", json={"case_name": "C"})
    cid = r.json()["case_id"]
    r = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f", "evidence_type": "BIN", "file_size": 1})
    eid = r.json()["evidence_id"]
    
    def raise_runtime(*args, **kwargs):
        raise RuntimeError("Secret error message")
    monkeypatch.setattr(CalibrationRepository, "insert_and_supersede", raise_runtime)
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        CalibrationService.set_calibration(eid, CalibrationCreate(device_time="2026-01-01T00:00:00Z", reference_time="2026-01-01T00:00:00Z", uncertainty_seconds=0))
    assert exc.value.status_code == 500
    assert exc.value.detail == "Internal error while saving calibration"
    assert "Secret" not in exc.value.detail
    
    rows = client.get(f"/api/audit-log?evidence_id={eid}&limit=500").json()
    last = [r for r in rows if r["action"] == "CALIBRATION_SET"][-1]
    assert last["action"] == "CALIBRATION_SET"
    assert last["outcome"] == "ERROR"
    assert last["details"]["reason"] == "INTERNAL_ERROR"

def test_service_sorting_fractional(client):
    from app.repositories.metadata_repository import MetadataRepository
    r = client.post("/api/cases", json={"case_name": "C"})
    cid = r.json()["case_id"]
    r1 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f", "evidence_type": "BIN", "file_size": 1})
    eid1 = r1.json()["evidence_id"]
    r2 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f2", "evidence_type": "BIN", "file_size": 1})
    eid2 = r2.json()["evidence_id"]
    
    # event 1: whole second
    fields1 = [{"field": "creation_time", "raw_value": 1, "interpreted_value": "2026-01-01T10:00:00Z", "source": "s", "byte_offset": 1}]
    MetadataRepository.upsert("EVIDENCE", eid1, cid, "M", "1", "OK", {"fields": fields1}, "2026-01-01T00:00:00Z")
    
    # event 2: half second AFTER
    fields2 = [{"field": "creation_time", "raw_value": 1, "interpreted_value": "2026-01-01T10:00:00.500000Z", "source": "s", "byte_offset": 1}]
    MetadataRepository.upsert("EVIDENCE", eid2, cid, "M", "1", "OK", {"fields": fields2}, "2026-01-01T00:00:00Z")
    
    j = client.get(f"/api/cases/{cid}/calibrated-times").json()
    items = j["items"]
    assert items[0]["evidence_id"] == eid1
    assert items[1]["evidence_id"] == eid2

def test_history_order(client):
    r = client.post("/api/cases", json={"case_name": "C"})
    cid = r.json()["case_id"]
    r = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f", "evidence_type": "BIN", "file_size": 1})
    eid = r.json()["evidence_id"]
    
    CalibrationRepository.insert_and_supersede("r1", eid, cid, "dev", "ref", 1.0, 0.0, None, [], "e1", "U")
    CalibrationRepository.insert_and_supersede("r2", eid, cid, "dev", "ref", 2.0, 0.0, None, [], "e1", "U")
    CalibrationRepository.insert_and_supersede("r3", eid, cid, "dev", "ref", 3.0, 0.0, None, [], "e1", "U")
    
    j = client.get(f"/api/evidence/{eid}/calibration").json()
    hist = j["history"]
    assert hist[0]["reference_id"] == "r3"
    assert hist[1]["reference_id"] == "r2"
    assert hist[2]["reference_id"] == "r1"

def test_apply_offset_huge():
    dt = datetime.datetime(2026, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    with pytest.raises(OverflowError):
        apply_offset(dt, 1e15, 0.0)

def test_service_logger_exception(client, monkeypatch):
    r = client.post("/api/cases", json={"case_name": "C"})
    cid = r.json()["case_id"]
    r = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f", "evidence_type": "BIN", "file_size": 1})
    eid = r.json()["evidence_id"]
    
    def raise_runtime(*args, **kwargs):
        raise RuntimeError("C:\\secret")
    monkeypatch.setattr(CalibrationRepository, "insert_and_supersede", raise_runtime)
    
    j = client.post(f"/api/evidence/{eid}/calibration", json={"device_time": "2026-01-01T00:00:00Z", "reference_time": "2026-01-01T00:00:00Z", "uncertainty_seconds": 0})
    assert j.status_code == 500
    assert "secret" not in j.text

def test_calibrated_times_invalid_dt(client, monkeypatch):
    r = client.post("/api/cases", json={"case_name": "C"})
    cid = r.json()["case_id"]
    r = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f", "evidence_type": "BIN", "file_size": 1})
    eid = r.json()["evidence_id"]
    
    from app.repositories.metadata_repository import MetadataRepository
    fields = [{"field": "creation_time", "raw_value": 1, "interpreted_value": "garbage", "source": "s", "byte_offset": 1}]
    MetadataRepository.upsert("EVIDENCE", eid, cid, "M", "1", "OK", {"fields": fields}, "2026-01-01T00:00:00Z")
    
    def mock_parse(ts):
        return None, ""
    
    import app.services.calibration_service
    monkeypatch.setattr(app.services.calibration_service, "parse_to_datetime", mock_parse)
    
    j = client.get(f"/api/cases/{cid}/calibrated-times").json()
    assert j["items"] == []


def test_superseded_reference_not_used_in_calibrated_times(client):
    from app.repositories.metadata_repository import MetadataRepository
    cid = client.post("/api/cases", json={"case_name": "C"}).json()["case_id"]
    eid = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "f", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    MetadataRepository.upsert("EVIDENCE", eid, cid, "MP4", "1", "OK",
        {"fields": [{"field": "creation_time", "raw_value": 1, "interpreted_value": "2025-06-01T10:00:00Z", "source": "s", "byte_offset": 1, "note": None}]}, "2026-01-01T00:00:00Z")
    body = {"device_time": "2026-01-01T10:00:00Z", "uncertainty_seconds": 0}
    client.post(f"/api/evidence/{eid}/calibration", json={**body, "reference_time": "2026-01-01T10:00:30Z"})
    client.post(f"/api/evidence/{eid}/calibration", json={**body, "reference_time": "2026-01-01T10:00:05Z"})
    j = client.get(f"/api/cases/{cid}/calibrated-times").json()
    assert j["items"][0]["corrected"]["nominal"] == "2025-06-01T10:00:05Z"


def test_get_active_for_case_returns_only_active_rows():
    from app.repositories.calibration_repository import CalibrationRepository as R
    for rid, ts in (("r1", "T1"), ("r2", "T2"), ("r3", "T3")):
        R.insert_and_supersede(rid, "e1", "c1", "2026-01-01T10:00:00Z", "2026-01-01T10:00:05Z", 5.0, 1.0, None, [], ts, "UNAUTHENTICATED")
    rows = R.get_active_for_case("c1")
    assert [r["reference_id"] for r in rows] == ["r3"]
