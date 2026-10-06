import os
import stat
import hashlib
from pathlib import Path

def create_case(client):
    return client.post("/api/cases", json={"case_name": "Test"}).json()["case_id"]

def register_evidence(client, case_id, file_size=3):
    return client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "test.bin",
        "evidence_type": "BIN",
        "file_size": file_size
    }).json()["evidence_id"]

def test_hash_abc(client, tmp_path):
    """Proves hash of 'abc' equals the known SHA-256."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id)
    test_file = tmp_path / "abc.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("abc.bin", f)})
        
    resp = client.post(f"/api/evidence/{ev_id}/hash")
    assert resp.status_code == 200
    assert resp.json()["status"] == "HASHED"
    assert resp.json()["sha256"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

def test_hash_random_file(client, tmp_path):
    """Proves hash of a random file matches standard hashlib computation."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, 1048576)
    
    test_file = tmp_path / "rand.bin"
    data = os.urandom(1048576)
    test_file.write_bytes(data)
    
    h = hashlib.sha256()
    h.update(data)
    expected_hash = h.hexdigest()
    
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("rand.bin", f)})
        
    resp = client.post(f"/api/evidence/{ev_id}/hash")
    assert resp.json()["sha256"] == expected_hash

def test_verify_success(client, tmp_path):
    """Proves verify returns match true consistently without changing record."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id)
    test_file = tmp_path / "abc.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("abc.bin", f)})
    client.post(f"/api/evidence/{ev_id}/hash")
    
    resp1 = client.post(f"/api/evidence/{ev_id}/verify")
    assert resp1.status_code == 200
    assert resp1.json()["match"] is True
    
    resp2 = client.post(f"/api/evidence/{ev_id}/verify")
    assert resp2.json()["match"] is True

def test_hash_twice_fails(client, tmp_path):
    """Proves baseline hash cannot be replaced."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id)
    test_file = tmp_path / "abc.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("abc.bin", f)})
    client.post(f"/api/evidence/{ev_id}/hash")
    
    resp = client.post(f"/api/evidence/{ev_id}/hash")
    assert resp.status_code == 409

def test_hash_registered_fails(client):
    """Proves hashing before ingestion fails."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id)
    assert client.post(f"/api/evidence/{ev_id}/hash").status_code == 409

def test_verify_ingested_fails(client, tmp_path):
    """Proves verifying before hashing fails."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id)
    test_file = tmp_path / "abc.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("abc.bin", f)})
        
    assert client.post(f"/api/evidence/{ev_id}/verify").status_code == 409

def test_unknown_hash_verify(client):
    """Proves hash and verify on unknown ID return 404."""
    assert client.post("/api/evidence/nonexistent/hash").status_code == 404
    assert client.post("/api/evidence/nonexistent/verify").status_code == 404

def test_tamper_simulation(client, tmp_path):
    """Proves tampering detects mismatch."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id)
    test_file = tmp_path / "abc.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("abc.bin", f)})
    client.post(f"/api/evidence/{ev_id}/hash")
    
    # Tamper
    stored = tmp_path / "raw" / case_id / ev_id
    os.chmod(stored, stat.S_IWRITE)
    with open(stored, "r+b") as f:
        f.seek(0)
        f.write(b"X")
        
    resp = client.post(f"/api/evidence/{ev_id}/verify")
    assert resp.status_code == 200
    assert resp.json()["match"] is False
    assert resp.json()["computed_sha256"] != resp.json()["baseline_sha256"]

def test_missing_file_simulation(client, tmp_path):
    """Proves missing stored file is detected on verify."""
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id)
    test_file = tmp_path / "abc.bin"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("abc.bin", f)})
    client.post(f"/api/evidence/{ev_id}/hash")
    
    # Delete
    stored = tmp_path / "raw" / case_id / ev_id
    os.chmod(stored, stat.S_IWRITE)
    os.remove(stored)
    
    assert client.post(f"/api/evidence/{ev_id}/verify").status_code == 404
