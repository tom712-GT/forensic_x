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
