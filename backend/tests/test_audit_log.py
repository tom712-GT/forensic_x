import pytest
import sqlite3
import json
from datetime import datetime, timezone
from app.db import database
from app.db.database import get_connection
from app.repositories.audit_repository import AuditRepository

def test_audit_schema_exists(tmp_path, monkeypatch):
    test_db = tmp_path / "test_audit_x.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database._schema_initialized = False
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        assert cursor.fetchone() is not None
        
        # Check triggers
        cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='prevent_audit_log_update'")
        assert cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='prevent_audit_log_delete'")
        assert cursor.fetchone() is not None
        
        # Check version
        cursor.execute("PRAGMA user_version")
        assert cursor.fetchone()[0] == 4

def test_upgrade_from_v1(tmp_path, monkeypatch):
    test_db = tmp_path / "test_upgrade_x.db"
    
    # Create v1 DB manually
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            case_name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            description TEXT,
            source TEXT,
            acquisition_time TEXT,
            status TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            stored_size INTEGER,
            size_matches_declared INTEGER,
            ingested_at TEXT,
            stored_path TEXT,
            hash_algorithm TEXT,
            sha256 TEXT,
            hashed_at TEXT,
            format_detection TEXT,
            vendor_detection TEXT,
            FOREIGN KEY(case_id) REFERENCES cases(case_id)
        )
    """)
    cursor.execute("INSERT INTO cases (case_id, case_name, created_at, status) VALUES ('case-1', 'C1', '2023-01-01T00:00:00Z', 'OPEN')")
    cursor.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()
    
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database._schema_initialized = False
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA user_version")
        assert cursor.fetchone()[0] == 4
        
        cursor.execute("SELECT case_name FROM cases WHERE case_id = 'case-1'")
        assert cursor.fetchone()[0] == 'C1'
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        assert cursor.fetchone() is not None

def test_audit_log_is_append_only(tmp_path, monkeypatch):
    test_db = tmp_path / "test_append_x.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database._schema_initialized = False
    
    AuditRepository.insert(
        timestamp="2023-01-01T00:00:00Z",
        action="CASE_CREATE",
        outcome="SUCCESS",
        http_status=201,
        actor="UNAUTHENTICATED",
        details={},
        case_id="case-xyz"
    )
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT audit_id FROM audit_log LIMIT 1")
        audit_id = cursor.fetchone()[0]
        
        with pytest.raises(sqlite3.DatabaseError) as exc_update:
            cursor.execute("UPDATE audit_log SET outcome = 'REJECTED' WHERE audit_id = ?", (audit_id,))
        print(f"\nUpdate Exception: {exc_update.type.__name__}")
        
        with pytest.raises(sqlite3.DatabaseError) as exc_delete:
            cursor.execute("DELETE FROM audit_log WHERE audit_id = ?", (audit_id,))
        print(f"\nDelete Exception: {exc_delete.type.__name__}")
        
        cursor.execute("SELECT outcome FROM audit_log WHERE audit_id = ?", (audit_id,))
        assert cursor.fetchone()[0] == 'SUCCESS'

def test_audit_insert_is_parameterized(tmp_path, monkeypatch):
    test_db = tmp_path / "test_param_x.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database._schema_initialized = False
    
    malicious_id = "x'; DROP TABLE audit_log;--"
    long_id = "x" * 300
    
    AuditRepository.insert(
        timestamp="2023-01-01T00:00:00Z",
        action="TEST", outcome="SUCCESS", http_status=200, actor="UNAUTHENTICATED", details={},
        evidence_id=malicious_id
    )
    
    AuditRepository.insert(
        timestamp="2023-01-01T00:00:00Z",
        action="TEST", outcome="SUCCESS", http_status=200, actor="UNAUTHENTICATED", details={},
        evidence_id=long_id
    )
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        assert cursor.fetchone() is not None
        
        cursor.execute("SELECT evidence_id FROM audit_log ORDER BY audit_id ASC")
        rows = cursor.fetchall()
        
        assert rows[0][0] == malicious_id
        assert rows[1][0] == "x" * 100

def test_audit_lifecycle(client, tmp_path):
    from app.repositories.audit_repository import AuditRepository
    from app.repositories.evidence_repository import EvidenceRepository
    
    # CASE_CREATE
    case_resp = client.post("/api/cases", json={"case_name": "Audit Case"})
    case_id = case_resp.json()["case_id"]
    
    # EVIDENCE_REGISTER
    ev_resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "test.bin", "evidence_type": "VIDEO", "file_size": 4})
    ev_id = ev_resp.json()["evidence_id"]
    
    # EVIDENCE_INGEST
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"IMKH")
    with open(test_file, "rb") as f:
        ingest_resp = client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
        
    # EVIDENCE_HASH
    hash_resp = client.post(f"/api/evidence/{ev_id}/hash")
    ev_sha256 = hash_resp.json()["sha256"]
    
    # EVIDENCE_VERIFY
    verify_resp = client.post(f"/api/evidence/{ev_id}/verify")
    
    # FORMAT_DETECT
    fmt_resp = client.post(f"/api/evidence/{ev_id}/detect-format")
    
    # VENDOR_DETECT
    vnd_resp = client.post(f"/api/evidence/{ev_id}/detect-vendor")
    
    entries = AuditRepository.list_entries(case_id=case_id)
    assert len(entries) == 7
    
    actions = [e["action"] for e in entries]
    assert actions == ["CASE_CREATE", "EVIDENCE_REGISTER", "EVIDENCE_INGEST", "EVIDENCE_HASH", "EVIDENCE_VERIFY", "FORMAT_DETECT", "VENDOR_DETECT"]
    
    for e in entries:
        assert e["outcome"] == "SUCCESS"
        assert str(e["http_status"]).startswith("2")
        
    # Check details
    hash_detail = json.loads(entries[3]["details"])
    assert hash_detail["sha256"] == ev_sha256
    
    verify_detail = json.loads(entries[4]["details"])
    assert verify_detail["match"] is True

def test_rejected_attempts_are_logged(client, tmp_path, monkeypatch):
    from app.repositories.audit_repository import AuditRepository
    from app.services.evidence_service import EvidenceService
    
    case_resp = client.post("/api/cases", json={"case_name": "Rejections"})
    case_id = case_resp.json()["case_id"]
    
    ev_resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "test.bin", "evidence_type": "VIDEO", "file_size": 4})
    ev_id = ev_resp.json()["evidence_id"]
    
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"abcd")
    empty_file = tmp_path / "empty.bin"
    empty_file.write_bytes(b"")
    
    # hash before ingest
    client.post(f"/api/evidence/{ev_id}/hash")
    
    # verify before hash
    client.post(f"/api/evidence/{ev_id}/verify")
    
    # detect format before ingest
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    # ingest over limit
    monkeypatch.setattr("app.api.evidence.MAX_UPLOAD_BYTES", 2)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
    monkeypatch.setattr("app.api.evidence.MAX_UPLOAD_BYTES", 100*1024*1024)
    
    # empty upload
    with open(empty_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("empty.bin", f)})
        
    # success upload
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
        
    # second upload
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
        
    # hash twice
    client.post(f"/api/evidence/{ev_id}/hash")
    client.post(f"/api/evidence/{ev_id}/hash")
    
    entries = AuditRepository.list_entries(evidence_id=ev_id)
    rejections = [e for e in entries if e["outcome"] == "REJECTED"]
    
    reasons = [json.loads(e["details"]).get("reason") for e in rejections]
    assert "NOT_INGESTED" in reasons
    assert "NOT_HASHED" in reasons
    assert "FILE_TOO_LARGE" in reasons
    assert "EMPTY_FILE" in reasons
    assert "ALREADY_INGESTED" in reasons
    assert "ALREADY_HASHED" in reasons

def test_unknown_ids_are_logged(client):
    from app.repositories.audit_repository import AuditRepository
    client.post("/api/evidence/random-ev/hash")
    client.post("/api/cases/random-case/evidence", json={"original_filename": "a", "evidence_type": "VIDEO", "file_size": 1})
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT action, outcome, details FROM audit_log WHERE outcome='NOT_FOUND'")
        rows = cursor.fetchall()
        reasons = [json.loads(r["details"]).get("reason") for r in rows]
        assert "UNKNOWN_EVIDENCE" in reasons
        assert "UNKNOWN_CASE" in reasons

def test_verify_mismatch_is_integrity_failure(client, tmp_path):
    from app.repositories.audit_repository import AuditRepository
    from app.repositories.evidence_repository import EvidenceRepository
    
    case_resp = client.post("/api/cases", json={"case_name": "Tamper Case"})
    case_id = case_resp.json()["case_id"]
    ev_resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "a", "evidence_type": "VIDEO", "file_size": 3})
    ev_id = ev_resp.json()["evidence_id"]
    
    test_file = tmp_path / "a.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("a.bin", f)})
        
    client.post(f"/api/evidence/{ev_id}/hash")
    
    ev_db = EvidenceRepository.get_by_id(ev_id)
    import os, stat
    os.chmod(ev_db.stored_path, stat.S_IWRITE)
    with open(ev_db.stored_path, "wb") as f:
        f.write(b"tampered")
        
    client.post(f"/api/evidence/{ev_id}/verify")
    
    entries = AuditRepository.list_entries(evidence_id=ev_id)
    verify_entry = next(e for e in entries if e["action"] == "EVIDENCE_VERIFY")
    assert verify_entry["outcome"] == "INTEGRITY_FAILURE"
    assert verify_entry["http_status"] == 200
    
    det = json.loads(verify_entry["details"])
    assert det["match"] is False
    assert "baseline_sha256" in det
    assert "computed_sha256" in det

def test_verify_missing_file_is_logged(client, tmp_path):
    from app.repositories.audit_repository import AuditRepository
    from app.repositories.evidence_repository import EvidenceRepository
    import os
    
    case_resp = client.post("/api/cases", json={"case_name": "Missing Case"})
    case_id = case_resp.json()["case_id"]
    ev_resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "a", "evidence_type": "VIDEO", "file_size": 3})
    ev_id = ev_resp.json()["evidence_id"]
    
    test_file = tmp_path / "a.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("a.bin", f)})
        
    client.post(f"/api/evidence/{ev_id}/hash")
    
    ev_db = EvidenceRepository.get_by_id(ev_id)
    import stat
    os.chmod(ev_db.stored_path, stat.S_IWRITE)
    os.remove(ev_db.stored_path)
        
    client.post(f"/api/evidence/{ev_id}/verify")
    
    entries = AuditRepository.list_entries(evidence_id=ev_id)
    verify_entry = next(e for e in entries if e["action"] == "EVIDENCE_VERIFY")
    assert verify_entry["outcome"] == "NOT_FOUND"
    det = json.loads(verify_entry["details"])
    assert det["reason"] == "STORED_FILE_MISSING"

def test_unexpected_error_is_logged_generic(client, monkeypatch, tmp_path):
    from app.services.evidence_service import EvidenceService
    from app.repositories.audit_repository import AuditRepository
    
    def mock_hash(*args, **kwargs):
        raise RuntimeError("D:\\secret\\x")
        
    monkeypatch.setattr(EvidenceService, "hash_evidence", mock_hash)
    
    case_resp = client.post("/api/cases", json={"case_name": "Error Case"})
    case_id = case_resp.json()["case_id"]
    ev_resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "a", "evidence_type": "VIDEO", "file_size": 3})
    ev_id = ev_resp.json()["evidence_id"]
    
    test_file = tmp_path / "a.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("a.bin", f)})
        
    client.post(f"/api/evidence/{ev_id}/hash")
    
    entries = AuditRepository.list_entries(evidence_id=ev_id)
    err_entry = next(e for e in entries if e["action"] == "EVIDENCE_HASH")
    assert err_entry["outcome"] == "ERROR"
    det = json.loads(err_entry["details"])
    assert det["reason"] == "INTERNAL_ERROR"
    
    # Check secret nowhere
    for e in entries:
        assert "secret" not in e["details"]
        assert "secret" not in str(e)

def test_audit_has_no_paths(client, tmp_path):
    from app.repositories.audit_repository import AuditRepository
    from app.services.evidence_service import RAW_STORAGE_ROOT
    
    entries = AuditRepository.list_entries()
    for e in entries:
        det = e["details"]
        assert "stored_path" not in det
        assert str(RAW_STORAGE_ROOT) not in det

def test_audit_failure_does_not_break_requests(client, monkeypatch, tmp_path):
    from app.repositories.audit_repository import AuditRepository
    
    def mock_insert(*args, **kwargs):
        raise Exception("DB Down")
        
    monkeypatch.setattr(AuditRepository, "insert", mock_insert)
    
    case_resp = client.post("/api/cases", json={"case_name": "Audit Fail Case"})
    assert case_resp.status_code == 201
    case_id = case_resp.json()["case_id"]
    
    ev_resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "a", "evidence_type": "VIDEO", "file_size": 3})
    assert ev_resp.status_code == 201

def test_audit_endpoint_filters_and_order(client, tmp_path):
    case_resp = client.post("/api/cases", json={"case_name": "Read Test Case"})
    case_id = case_resp.json()["case_id"]
    
    ev_resp1 = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "1.bin", "evidence_type": "VIDEO", "file_size": 1})
    ev1_id = ev_resp1.json()["evidence_id"]
    
    ev_resp2 = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "2.bin", "evidence_type": "VIDEO", "file_size": 2})
    ev2_id = ev_resp2.json()["evidence_id"]
    
    # query case_id
    resp_case = client.get(f"/api/audit-log?case_id={case_id}")
    assert resp_case.status_code == 200
    rows = resp_case.json()
    assert len(rows) == 3 # case create + 2 evidence register
    
    # verify order by audit_id ascending
    audit_ids = [r["audit_id"] for r in rows]
    assert audit_ids == sorted(audit_ids)
    
    # query evidence_id
    resp_ev = client.get(f"/api/audit-log?evidence_id={ev1_id}")
    assert resp_ev.status_code == 200
    ev_rows = resp_ev.json()
    assert len(ev_rows) == 1
    assert ev_rows[0]["action"] == "EVIDENCE_REGISTER"
    assert ev_rows[0]["evidence_id"] == ev1_id
    
    # limit works
    resp_limit = client.get(f"/api/audit-log?case_id={case_id}&limit=2")
    assert resp_limit.status_code == 200
    assert len(resp_limit.json()) == 2
    
    # limits out of bounds
    assert client.get("/api/audit-log?limit=0").status_code == 422
    assert client.get("/api/audit-log?limit=501").status_code == 422

def test_audit_endpoint_timestamps_and_actor(client):
    case_resp = client.post("/api/cases", json={"case_name": "Time Case"})
    case_id = case_resp.json()["case_id"]
    
    resp = client.get(f"/api/audit-log?case_id={case_id}")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0
    
    for r in rows:
        assert r["timestamp"].endswith("Z")
        assert r["actor"] == "UNAUTHENTICATED"

def test_audit_survives_restart(client, tmp_path):
    case_resp = client.post("/api/cases", json={"case_name": "Restart Case"})
    case_id = case_resp.json()["case_id"]
    
    ev_resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "a", "evidence_type": "VIDEO", "file_size": 4})
    ev_id = ev_resp.json()["evidence_id"]
    
    test_file = tmp_path / "a.bin"
    test_file.write_bytes(b"IMKH")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("a.bin", f)})
        
    client.post(f"/api/evidence/{ev_id}/hash")
    
    resp_before = client.get(f"/api/audit-log?evidence_id={ev_id}")
    before_data = resp_before.json()
    
    import subprocess
    from app.db.database import DB_PATH
    from app.services.evidence_service import RAW_STORAGE_ROOT
    
    code = f"""
import sys
sys.path.append(r'D:\\FORENSIC-X\\backend')
from fastapi.testclient import TestClient
from app.main import app
import app.db.database as db
from pathlib import Path
db.DB_PATH = Path(r'{DB_PATH}')
db._schema_initialized = False

client = TestClient(app)
resp = client.get("/api/audit-log?evidence_id={ev_id}")
print(resp.json())
"""
    
    script_path = tmp_path / "restart.py"
    script_path.write_text(code, encoding="utf-8")
    
    import sys
    result = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, check=True)
    import ast
    after_data = ast.literal_eval(result.stdout.strip())
    
    assert before_data == after_data
