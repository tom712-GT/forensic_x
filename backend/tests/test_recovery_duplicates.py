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
    
    # 1. Recover first time
    res = client.post(f"/api/evidence/{evidence_id}/recover")
    assert res.status_code == 200
    artifacts1 = res.json()
    assert len(artifacts1) == 1
    
    # Verify the physical file exists
    from app.services.recovery_service import RECOVERED_STORAGE_ROOT
    recovered_dir = RECOVERED_STORAGE_ROOT / case_id / evidence_id
    physical_files_before = list(recovered_dir.iterdir())
    assert len(physical_files_before) == 1
    
    # 2. Recover again. Should not create duplicate DB rows or files.
    res2 = client.post(f"/api/evidence/{evidence_id}/recover")
    assert res2.status_code == 200
    assert len(res2.json()) == 0
    
    physical_files_after = list(recovered_dir.iterdir())
    assert len(physical_files_after) == 1
    assert physical_files_before[0].name == physical_files_after[0].name

def test_recovery_candidate_semantics(tmp_path):
    res = client.post("/api/cases", json={"case_name": "Candidate", "description": "Candidate"})
    case_id = res.json()["case_id"]

    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "cand.dd",
        "evidence_type": "IMAGE",
        "file_size": 1000
    })
    evidence_id = res.json()["evidence_id"]

    # Valid ZIP Candidate embedded
    file_content = b"\x00" * 100 + b"PK\x03\x04" + b"fake_zip_data" + b"\x00" * 100
    test_file = tmp_path / "cand.dd"
    test_file.write_bytes(file_content)
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{evidence_id}/file", files={"file": ("cand.dd", f)})
        
    client.post(f"/api/evidence/{evidence_id}/hash")
    
    res = client.post(f"/api/evidence/{evidence_id}/recover")
    assert res.status_code == 200
    artifacts = res.json()
    assert len(artifacts) == 1
    a = artifacts[0]
    
    assert a["detected_type"] == "ZIP"
    assert a["status"] == "CANDIDATE"
    
    from app.services.recovery_service import RECOVERED_STORAGE_ROOT
    recovered_dir = RECOVERED_STORAGE_ROOT / case_id / evidence_id
    physical_files = list(recovered_dir.iterdir())
    assert len(physical_files) == 1
    assert physical_files[0].name.endswith(".bin")
    
def test_db_failure_cleanup(tmp_path, monkeypatch):
    res = client.post("/api/cases", json={"case_name": "FailCleanup", "description": "Fail"})
    case_id = res.json()["case_id"]

    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "fail.dd",
        "evidence_type": "IMAGE",
        "file_size": 1000
    })
    evidence_id = res.json()["evidence_id"]

    file_content = b"\x00" * 100 + b"\xff\xd8\xff" + b"fake_jpeg_data" + b"\xff\xd9" + b"\x00" * 100
    test_file = tmp_path / "fail.dd"
    test_file.write_bytes(file_content)
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{evidence_id}/file", files={"file": ("fail.dd", f)})
        
    client.post(f"/api/evidence/{evidence_id}/hash")
    
    from app.repositories.recovery_repository import RecoveryRepository
    def mock_insert(*args, **kwargs):
        raise RuntimeError("Fake DB Failure")
        
    monkeypatch.setattr(RecoveryRepository, "insert", mock_insert)
    
    res = client.post(f"/api/evidence/{evidence_id}/recover")
    assert res.status_code == 500
    
    # Check that no orphan files exist
    from app.services.recovery_service import RECOVERED_STORAGE_ROOT
    recovered_dir = RECOVERED_STORAGE_ROOT / case_id / evidence_id
    assert len(list(recovered_dir.iterdir())) == 0

def test_sqlite_unique_constraint(tmp_path):
    from app.models.recovery import RecoveredArtifact
    from app.repositories.recovery_repository import RecoveryRepository
    import sqlite3
    
    res = client.post("/api/cases", json={"case_name": "Constraint", "description": "Constraint"})
    case_id = res.json()["case_id"]

    res = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "const.dd",
        "evidence_type": "IMAGE",
        "file_size": 1000
    })
    evidence_id = res.json()["evidence_id"]
    
    artifact1 = RecoveredArtifact(
        evidence_id=evidence_id,
        case_id=case_id,
        source_offset=100,
        recovered_size=50,
        detected_type="JPEG",
        output_path="dummy/path.jpeg",
        artifact_hash="abc",
        status="RECOVERED"
    )
    
    artifact2 = RecoveredArtifact(
        evidence_id=evidence_id,
        case_id=case_id,
        source_offset=100,
        recovered_size=50,
        detected_type="JPEG",
        output_path="dummy/path2.jpeg",
        artifact_hash="def",
        status="RECOVERED"
    )
    
    # Manually insert to test constraint
    RecoveryRepository.insert(artifact1)
    
    with pytest.raises(sqlite3.IntegrityError):
        RecoveryRepository.insert(artifact2)
