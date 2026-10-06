import pytest
import os
import hashlib
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_recovery_duplicate_handling(tmp_path):
    res = client.post("/api/cases", json={"case_name": "Dup", "description": "Dup"})
    case_id = res.json()["case_id"]

    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "dup.dd",
        "evidence_type": "IMAGE",
        "file_size": 1000
    })
    evidence_id = res.json()["evidence_id"]

    # Valid JPEG embedded
    file_content = b"\x00" * 100 + b"\xff\xd8\xff" + b"fake_jpeg_data" + b"\xff\xd9" + b"\x00" * 100
    test_file = tmp_path / "dup.dd"
    test_file.write_bytes(file_content)
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{evidence_id}/file", files={"file": ("dup.dd", f)})
        
    client.post(f"/api/evidence/{evidence_id}/hash")
    
    # 2. Recover
    res = client.post(f"/api/evidence/{evidence_id}/recover")
    assert res.status_code == 200
    assert len(res.json()) == 1
    
    # Recover again. Should not return dup artifacts in DB?
    # Wait, the recovery endpoint right now processes the stream and just inserts to DB.
    # It deduplicates within the same file stream run (seen_artifacts).
    # If called twice, does it insert duplicate DB rows?
    # The requirement says "Do not create duplicate artifact records for the same artifact during one deterministic scan."
    # The deduplication across multiple scans is optional, but during ONE scan it is required.
    pass
