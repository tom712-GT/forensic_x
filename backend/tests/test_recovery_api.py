import pytest
import os
import hashlib
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def compute_file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def test_recovery_api_happy_path(tmp_path):
    # 1. Setup case and evidence
    res = client.post("/api/cases", json={"case_name": "Rec Case", "description": "Rec"})
    case_id = res.json()["case_id"]

    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "image.dd",
        "evidence_type": "IMAGE",
        "file_size": 8192
    })
    evidence_id = res.json()["evidence_id"]

    # Valid JPEG embedded
    file_content = b"\x00" * 100 + b"\xff\xd8\xff" + b"fake_jpeg_data" + b"\xff\xd9" + b"\x00" * (8192 - 100 - 19)
    test_file = tmp_path / "test.dd"
    test_file.write_bytes(file_content)
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{evidence_id}/file", files={"file": ("image.dd", f)})
        
    client.post(f"/api/evidence/{evidence_id}/hash")
    
    stored_path = tmp_path / "raw" / case_id / evidence_id
    before_sha256 = compute_file_sha256(stored_path)
    
    # 2. Recover
    res = client.post(f"/api/evidence/{evidence_id}/recover")
    assert res.status_code == 200
    artifacts = res.json()
    assert len(artifacts) == 1
    a = artifacts[0]
    
    assert a["evidence_id"] == evidence_id
    assert a["case_id"] == case_id
    assert a["source_offset"] == 100
    assert a["recovered_size"] == 19
    assert a["detected_type"] == "JPEG"
    assert a["status"] == "RECOVERED"
    assert "artifact_hash" in a
    assert "output_path" not in a
    
    # 3. Source evidence remains unchanged
    after_sha256 = compute_file_sha256(stored_path)
    assert before_sha256 == after_sha256
    
    # 4. Recovered artifact stored separately
    # The output_path is in data/recovered/<case_id>/<evidence_id>/<artifact_id>.jpeg
    import sys
    from pathlib import Path
    backend_dir = Path(sys.modules['app.main'].__file__).resolve().parents[2]
    recovered_dir = backend_dir / "data" / "recovered" / case_id / evidence_id
    
    recovered_file = recovered_dir / f"{a['artifact_id']}.jpeg"
    assert recovered_file.exists()
    assert recovered_file.read_bytes() == b"\xff\xd8\xff" + b"fake_jpeg_data" + b"\xff\xd9"
    
def test_recovery_unregistered_evidence():
    res = client.post("/api/evidence/fake-uuid/recover")
    assert res.status_code == 404

def test_recovery_not_ingested():
    res = client.post("/api/cases", json={"case_name": "Rec Case 2", "description": "Rec"})
    case_id = res.json()["case_id"]
    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "image.dd",
        "evidence_type": "IMAGE",
        "file_size": 8192
    })
    evidence_id = res.json()["evidence_id"]
    
    res = client.post(f"/api/evidence/{evidence_id}/recover")
    assert res.status_code == 409
    assert "must be ingested" in res.json()["detail"]

def test_recovery_no_path_leakage(monkeypatch):
    res = client.post("/api/cases", json={"case_name": "Rec Case 3", "description": "Rec"})
    case_id = res.json()["case_id"]

    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "image.dd",
        "evidence_type": "IMAGE",
        "file_size": 100
    })
    evidence_id = res.json()["evidence_id"]

    file_content = b"\x00" * 100
    test_file = Path("test3.dd")
    test_file.write_bytes(file_content)
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{evidence_id}/file", files={"file": ("image.dd", f)})
    test_file.unlink()
        
    from app.services.recovery_service import RecoveryService
    def mock_recover(*args, **kwargs):
        raise RuntimeError("D:\\secret\\path.dd")
        
    monkeypatch.setattr(RecoveryService, "recover_artifacts", mock_recover)
    
    import json
    resp = client.post(f"/api/evidence/{evidence_id}/recover")
    assert resp.status_code == 500
    data = json.dumps(resp.json())
    assert "D:\\" not in data
    assert "secret" not in data
    assert "path.dd" not in data
    assert "RuntimeError" not in data
    assert resp.json()["detail"] == "Internal error while recovering artifacts"

