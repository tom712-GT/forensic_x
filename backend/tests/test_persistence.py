import os
import sys
import subprocess
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pytest
import app.db.database as database
from app.repositories.evidence_repository import EvidenceRepository

def test_db_path_is_isolated(tmp_path):
    assert str(database.DB_PATH).startswith(str(tmp_path))
    assert "forensic_x.db" not in str(database.DB_PATH) # Since we use test.db

def test_restart_keeps_data(client, tmp_path):
    case_resp = client.post("/api/cases", json={"case_name": "Restart Case"})
    case_id = case_resp.json()["case_id"]
    
    ev_resp = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "test.mp4",
        "evidence_type": "BIN",
        "file_size": 1024
    })
    ev_id = ev_resp.json()["evidence_id"]
    
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    client.post(f"/api/evidence/{ev_id}/hash")
    client.post(f"/api/evidence/{ev_id}/detect-format")
    client.post(f"/api/evidence/{ev_id}/detect-vendor")
    
    cases_list = client.get("/api/cases").json()
    case_obj = client.get(f"/api/cases/{case_id}").json()
    case_ev_list = client.get(f"/api/cases/{case_id}/evidence").json()
    ev_obj = client.get(f"/api/evidence/{ev_id}").json()
    
    db_path_str = str(database.DB_PATH)
    raw_path_str = str(tmp_path / "raw")
    
    script = """
import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

db_path = Path(sys.argv[1])
raw_path = Path(sys.argv[2])

import app.db.database as database
import app.services.evidence_service as evidence_service
database.DB_PATH = db_path
database._schema_initialized = False
evidence_service.RAW_STORAGE_ROOT = raw_path

from app.main import app

client = TestClient(app)
cases_list = client.get("/api/cases").json()
case_obj = client.get(f"/api/cases/{sys.argv[3]}").json()
case_ev_list = client.get(f"/api/cases/{sys.argv[3]}/evidence").json()
ev_obj = client.get(f"/api/evidence/{sys.argv[4]}").json()
verify_obj = client.post(f"/api/evidence/{sys.argv[4]}/verify").json()

print(json.dumps({
    "cases_list": cases_list,
    "case_obj": case_obj,
    "case_ev_list": case_ev_list,
    "ev_obj": ev_obj,
    "verify": verify_obj
}))
"""
    
    backend_dir = str(Path(__file__).resolve().parents[1])
    res = subprocess.run(
        [sys.executable, "-c", script, db_path_str, raw_path_str, case_id, ev_id],
        cwd=backend_dir,
        capture_output=True,
        text=True
    )
    
    assert res.returncode == 0, res.stderr
    
    restarted_data = json.loads(res.stdout)
    
    assert restarted_data["cases_list"] == cases_list
    assert restarted_data["case_obj"] == case_obj
    assert restarted_data["case_ev_list"] == case_ev_list
    assert restarted_data["ev_obj"] == ev_obj
    
    assert restarted_data["verify"]["match"] is True
    assert restarted_data["verify"]["baseline_sha256"] == ev_obj["sha256"]

def test_list_order_preserved(client):
    case_ids = []
    for i in range(3):
        r = client.post("/api/cases", json={"case_name": f"Case {i}"})
        case_ids.append(r.json()["case_id"])
        
    c0 = case_ids[0]
    ev_ids = []
    for i in range(3):
        r = client.post(f"/api/cases/{c0}/evidence", json={
            "original_filename": f"f{i}.bin",
            "evidence_type": "BIN",
            "file_size": 100
        })
        ev_ids.append(r.json()["evidence_id"])
        
    cases = client.get("/api/cases").json()
    assert [c["case_id"] for c in cases] == case_ids
    
    evidence = client.get(f"/api/cases/{c0}/evidence").json()
    assert [e["evidence_id"] for e in evidence] == ev_ids

def test_hash_baseline_cannot_be_overwritten_in_db(client, tmp_path):
    case_id = client.post("/api/cases", json={"case_name": "Hash Case"}).json()["case_id"]
    ev_id = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "test.mp4",
        "evidence_type": "BIN",
        "file_size": 4
    }).json()["evidence_id"]
    
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"abcd")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    client.post(f"/api/evidence/{ev_id}/hash")
    
    original_hash = client.get(f"/api/evidence/{ev_id}").json()["sha256"]
    
    # Try to overwrite directly using repository
    changed = EvidenceRepository.update_hash(ev_id, "different_hash", "SHA-256", datetime.now(timezone.utc))
    assert changed is False
    
    # Assert DB unchanged
    current_hash = client.get(f"/api/evidence/{ev_id}").json()["sha256"]
    assert current_hash == original_hash

def test_foreign_key_enforced(client):
    from app.models.evidence import Evidence
    ev = Evidence(
        case_id="nonexistent-case",
        original_filename="a",
        evidence_type="b",
        file_size=1
    )
    with pytest.raises(sqlite3.IntegrityError):
        EvidenceRepository.insert(ev)

def test_each_detection_saves_only_its_column(client, tmp_path):
    case_id = client.post("/api/cases", json={"case_name": "Detection Case"}).json()["case_id"]
    ev_id = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "test.mp4",
        "evidence_type": "BIN",
        "file_size": 1024
    }).json()["evidence_id"]
    
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    client.post(f"/api/evidence/{ev_id}/hash")
    
    with database.get_connection() as conn:
        row_after_hash = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (ev_id,)).fetchone()
    
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    with database.get_connection() as conn:
        row_after_format = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (ev_id,)).fetchone()
        
    client.post(f"/api/evidence/{ev_id}/detect-vendor")
    
    with database.get_connection() as conn:
        row_after_vendor = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (ev_id,)).fetchone()
        
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    with database.get_connection() as conn:
        row_final = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (ev_id,)).fetchone()
        
    import json
    
    # Assert format_detection changed after detect-format, but vendor did not exist
    assert row_after_format["format_detection"] is not None
    assert row_after_format["vendor_detection"] is None
    
    # Assert vendor_detection changed after detect-vendor, but format stayed same
    assert row_after_vendor["vendor_detection"] is not None
    assert row_after_vendor["format_detection"] == row_after_format["format_detection"]
    
    # Assert running format again didn't change vendor
    assert row_final["vendor_detection"] == row_after_vendor["vendor_detection"]
    
    # Assert other columns are unchanged
    assert row_final["sha256"] == row_after_hash["sha256"]
    assert row_final["hashed_at"] == row_after_hash["hashed_at"]
    assert row_final["status"] == row_after_hash["status"]
    assert row_final["stored_path"] == row_after_hash["stored_path"]

def test_detection_timestamps_match_other_timestamps(client, tmp_path):
    case_id = client.post("/api/cases", json={"case_name": "Timestamp Case"}).json()["case_id"]
    ev_id = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "test.mp4",
        "evidence_type": "BIN",
        "file_size": 1024
    }).json()["evidence_id"]
    
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    hash_resp = client.post(f"/api/evidence/{ev_id}/hash").json()
    assert hash_resp["hashed_at"] is not None
    assert hash_resp["hashed_at"].endswith("Z")
    
    post_format_resp = client.post(f"/api/evidence/{ev_id}/detect-format").json()
    assert post_format_resp["format_detection"] is not None
    assert post_format_resp["format_detection"]["detected_at"].endswith("Z")
    
    post_vendor_resp = client.post(f"/api/evidence/{ev_id}/detect-vendor").json()
    assert post_vendor_resp["vendor_detection"] is not None
    assert post_vendor_resp["vendor_detection"]["detected_at"].endswith("Z")
    
    get_resp = client.get(f"/api/evidence/{ev_id}").json()
    
    assert get_resp["registered_at"] is not None
    assert get_resp["registered_at"].endswith("Z")
    assert get_resp["ingested_at"] is not None
    assert get_resp["ingested_at"].endswith("Z")
    assert get_resp["hashed_at"] is not None
    assert get_resp["hashed_at"].endswith("Z")
    assert get_resp["format_detection"] is not None
    assert get_resp["format_detection"]["detected_at"].endswith("Z")
    assert get_resp["vendor_detection"] is not None
    assert get_resp["vendor_detection"]["detected_at"].endswith("Z")

def test_schema_creation_is_repeatable(client):
    with database.get_connection() as conn:
        conn.execute("PRAGMA user_version = 0")
        
    database._schema_initialized = False
    
    with database.get_connection() as conn:
        tables = [row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "cases" in tables
        assert "evidence" in tables
