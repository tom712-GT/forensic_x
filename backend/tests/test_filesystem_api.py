import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_happy_path(tmp_path):
    # 1. Create Case
    res = client.post("/api/cases", json={"case_name": "FS Case", "description": "FS"})
    case_id = res.json()["case_id"]

    # 2. Register Evidence
    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "image.dd",
        "evidence_type": "IMAGE",
        "file_size": 8192
    })
    evidence_id = res.json()["evidence_id"]

    # 3. Ingest (NTFS signature)
    file_content = b"\x00\x00\x00NTFS    " + b"\x00" * (8192 - 11)
    test_file = tmp_path / "test.dd"
    test_file.write_bytes(file_content)
    
    with open(test_file, "rb") as f:
        res = client.post(f"/api/evidence/{evidence_id}/file", files={"file": ("image.dd", f)})
    assert res.status_code == 200

    # 4. Analyze Filesystem
    res = client.post(f"/api/evidence/{evidence_id}/analyze-filesystem")
    assert res.status_code == 200
    data = res.json()
    assert data["filesystem_analysis"]["container_type"] == "RAW"
    assert data["filesystem_analysis"]["filesystem_type"] == "NTFS"
    assert "detected_at" in data["filesystem_analysis"]

def test_unregistered_evidence_analyze():
    res = client.post("/api/evidence/fake-uuid/analyze-filesystem")
    assert res.status_code == 404

def test_not_ingested_analyze():
    res = client.post("/api/cases", json={"case_name": "FS Case 2", "description": "FS"})
    case_id = res.json()["case_id"]
    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "image.dd",
        "evidence_type": "IMAGE",
        "file_size": 8192
    })
    evidence_id = res.json()["evidence_id"]
    
    res = client.post(f"/api/evidence/{evidence_id}/analyze-filesystem")
    assert res.status_code == 409
    assert "must be ingested" in res.json()["detail"]

import hashlib
import os

def compute_file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def test_read_only_proof_and_unchanged(tmp_path):
    res = client.post("/api/cases", json={"case_name": "FS Case 3", "description": "FS"})
    case_id = res.json()["case_id"]

    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "image.dd",
        "evidence_type": "IMAGE",
        "file_size": 8192
    })
    evidence_id = res.json()["evidence_id"]

    file_content = b"\x00\x00\x00NTFS    " + b"\x00" * (8192 - 11)
    test_file = tmp_path / "test.dd"
    test_file.write_bytes(file_content)
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{evidence_id}/file", files={"file": ("image.dd", f)})
        
    client.post(f"/api/evidence/{evidence_id}/hash")
    
    before_resp = client.get(f"/api/evidence/{evidence_id}")
    before_data = before_resp.json()
    
    stored_path = tmp_path / "raw" / case_id / evidence_id
    before_sha256 = compute_file_sha256(stored_path)
    before_size = stored_path.stat().st_size
    before_mtime = stored_path.stat().st_mtime
    
    res = client.post(f"/api/evidence/{evidence_id}/analyze-filesystem")
    assert res.status_code == 200
    
    after_resp = client.get(f"/api/evidence/{evidence_id}")
    after_data = after_resp.json()
    
    after_sha256 = compute_file_sha256(stored_path)
    after_size = stored_path.stat().st_size
    after_mtime = stored_path.stat().st_mtime
    
    assert before_sha256 == after_sha256
    assert before_size == after_size
    assert before_mtime == after_mtime
    
    after_fs = after_data.pop("filesystem_analysis")
    before_fs = before_data.pop("filesystem_analysis")
    
    assert before_fs is None
    assert after_fs["filesystem_type"] == "NTFS"
    assert before_data == after_data
    
    verify_resp = client.post(f"/api/evidence/{evidence_id}/verify")
    assert verify_resp.json()["match"] is True

def test_no_path_leakage(tmp_path, monkeypatch):
    res = client.post("/api/cases", json={"case_name": "FS Case 4", "description": "FS"})
    case_id = res.json()["case_id"]

    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "image.dd",
        "evidence_type": "IMAGE",
        "file_size": 8192
    })
    evidence_id = res.json()["evidence_id"]

    file_content = b"\x00\x00\x00NTFS    " + b"\x00" * (8192 - 11)
    test_file = tmp_path / "test.dd"
    test_file.write_bytes(file_content)
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{evidence_id}/file", files={"file": ("image.dd", f)})
        
    from app.services.evidence_service import EvidenceService
    def mock_analyze(*args, **kwargs):
        raise RuntimeError("D:\\secret_marker\\internal\\path.dd")
        
    monkeypatch.setattr(EvidenceService, "analyze_evidence_filesystem", mock_analyze)
    
    import json
    resp = client.post(f"/api/evidence/{evidence_id}/analyze-filesystem")
    assert resp.status_code == 500
    data = json.dumps(resp.json())
    assert "D:\\" not in data
    assert "secret_marker" not in data
    assert "internal\\path.dd" not in data
    assert "RuntimeError" not in data
    assert resp.json()["detail"] == "Internal error while analyzing filesystem"
