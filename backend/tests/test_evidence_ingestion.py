import os
import stat
from pathlib import Path
import app.api.evidence as api_evidence

def create_case(client):
    return client.post("/api/cases", json={"case_name": "Test"}).json()["case_id"]

def register_evidence(client, case_id, file_size=5):
    return client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "test.bin",
        "evidence_type": "BIN",
        "file_size": file_size
    }).json()["evidence_id"]

def test_ingestion_happy_path(client, tmp_path):
    """Proves happy path ingestion works."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, file_size=3)
    
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"abc")
    
    with open(test_file, "rb") as f:
        resp = client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
        
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "INGESTED"
    assert data["stored_size"] == 3
    assert data["size_matches_declared"] is True
    
    # Confirm identical bytes and read-only
    stored = tmp_path / "raw" / case_id / ev_id
    assert stored.read_bytes() == b"abc"
    assert not bool(os.stat(stored).st_mode & stat.S_IWRITE)

def test_second_upload_fails(client, tmp_path):
    """Proves overwriting is refused."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, file_size=3)
    
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"abc")
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
        
    with open(test_file, "rb") as f:
        resp = client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
        
    assert resp.status_code == 409
    assert tmp_path.joinpath("raw", case_id, ev_id).read_bytes() == b"abc"

def test_unknown_evidence(client, tmp_path):
    """Proves uploading to unknown evidence returns 404."""
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        assert client.post("/api/evidence/nonexistent/file", files={"file": ("test.bin", f)}).status_code == 404

def test_empty_upload(client, tmp_path):
    """Proves empty upload is rejected and no file is left behind."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, file_size=0)
    
    test_file = tmp_path / "empty.bin"
    test_file.write_bytes(b"")
    
    with open(test_file, "rb") as f:
        resp = client.post(f"/api/evidence/{ev_id}/file", files={"file": ("empty.bin", f)})
        
    assert resp.status_code == 400
    assert not tmp_path.joinpath("raw", case_id, ev_id).exists()
    assert client.get(f"/api/evidence/{ev_id}").json()["status"] == "REGISTERED"

def test_size_mismatch(client, tmp_path):
    """Proves declared size mismatch sets size_matches_declared to false."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, file_size=500)
    
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"abc")
    
    with open(test_file, "rb") as f:
        resp = client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
        
    assert resp.status_code == 200
    data = resp.json()
    assert data["size_matches_declared"] is False
    assert data["file_size"] == 500
    assert data["stored_size"] == 3

def test_path_traversal(client, tmp_path):
    """Proves path traversal in filename is ignored."""
    case_id = create_case(client)
    resp = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "../../evil.E01",
        "evidence_type": "BIN",
        "file_size": 3
    })
    ev_id = resp.json()["evidence_id"]
    
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"abc")
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("../../evil.E01", f)})
        
    assert tmp_path.joinpath("raw", case_id, ev_id).exists()
    assert not Path("evil.E01").exists()

def test_no_path_leakage(client, tmp_path):
    """Proves responses do not leak file paths."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, file_size=3)
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
        
    import json
    data = json.dumps(client.get(f"/api/evidence/{ev_id}").json())
    assert "stored_path" not in data
    assert "data/raw" not in data

def test_upload_too_large(client, monkeypatch, tmp_path):
    """Proves files larger than MAX_UPLOAD_BYTES are rejected and cleaned up."""
    monkeypatch.setattr(api_evidence, "MAX_UPLOAD_BYTES", 1024)
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, file_size=2000)
    
    test_file = tmp_path / "big.bin"
    test_file.write_bytes(os.urandom(2000))
    
    with open(test_file, "rb") as f:
        resp = client.post(f"/api/evidence/{ev_id}/file", files={"file": ("big.bin", f)})
        
    assert resp.status_code == 413
    assert not tmp_path.joinpath("raw", case_id, ev_id).exists()
    assert client.get(f"/api/evidence/{ev_id}").json()["status"] == "REGISTERED"

def test_second_ingest_does_not_destroy_first_file(client, tmp_path):
    import io
    import starlette.datastructures
    from app.services.evidence_service import EvidenceService
    from app.repositories.evidence_repository import EvidenceRepository
    import hashlib
    import pytest

    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, file_size=10)
    
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"first-file")
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
        
    stored_path = tmp_path / "raw" / case_id / ev_id
    first_hash = hashlib.sha256(stored_path.read_bytes()).hexdigest()
    
    stale_evidence = EvidenceRepository.get_by_id(ev_id)
    status_before = stale_evidence.status
    stored_size_before = stale_evidence.stored_size
    stored_path_before = stale_evidence.stored_path
    
    with pytest.raises(FileExistsError):
        EvidenceService.ingest_evidence_file(
            stale_evidence,
            starlette.datastructures.UploadFile(file=io.BytesIO(b"second-file"), filename="x"),
            1000
        )
        
    assert stored_path.exists()
    assert hashlib.sha256(stored_path.read_bytes()).hexdigest() == first_hash
    
    current_evidence = EvidenceRepository.get_by_id(ev_id)
    assert current_evidence.status == status_before
    assert current_evidence.stored_size == stored_size_before
    assert current_evidence.stored_path == stored_path_before

def test_router_maps_file_exists_error(client, monkeypatch, tmp_path):
    from app.services.evidence_service import EvidenceService
    
    def mock_ingest(*args, **kwargs):
        raise FileExistsError("Some random internal python file exists error text")
        
    monkeypatch.setattr(EvidenceService, "ingest_evidence_file", mock_ingest)
    
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, file_size=3)
    
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"abc")
    
    with open(test_file, "rb") as f:
        resp = client.post(f"/api/evidence/{ev_id}/file", files={"file": ("test.bin", f)})
        
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Evidence already ingested"
