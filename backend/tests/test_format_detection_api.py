import os
import stat
from pathlib import Path

def create_case(client):
    return client.post("/api/cases", json={"case_name": "Test"}).json()["case_id"]

def register_evidence(client, case_id, filename="test.mp4", file_size=1024):
    return client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": filename,
        "evidence_type": "BIN",
        "file_size": file_size
    }).json()["evidence_id"]

def test_happy_path(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    resp = client.post(f"/api/evidence/{ev_id}/detect-format")
    assert resp.status_code == 200
    data = resp.json()
    assert data["format_detection"]["detected_format"] == "MP4_ISO_BMFF"
    assert data["status"] == "INGESTED"

def test_read_only_proof(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    client.post(f"/api/evidence/{ev_id}/hash")
    
    verify_resp1 = client.post(f"/api/evidence/{ev_id}/verify")
    hash1 = verify_resp1.json()["baseline_sha256"]
    
    # Run format detection
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    verify_resp2 = client.post(f"/api/evidence/{ev_id}/verify")
    assert verify_resp2.json()["match"] is True
    assert verify_resp2.json()["baseline_sha256"] == hash1
    
    assert client.get(f"/api/evidence/{ev_id}").json()["status"] == "HASHED"

def test_detect_twice(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    r1 = client.post(f"/api/evidence/{ev_id}/detect-format").json()
    r2 = client.post(f"/api/evidence/{ev_id}/detect-format").json()
    assert r1["format_detection"]["detected_format"] == r2["format_detection"]["detected_format"]

def test_registered_item(client):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    assert client.post(f"/api/evidence/{ev_id}/detect-format").status_code == 409

def test_unknown_id(client):
    assert client.post("/api/evidence/nonexistent/detect-format").status_code == 404

def test_missing_file(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    stored = tmp_path / "raw" / case_id / ev_id
    os.chmod(stored, stat.S_IWRITE)
    os.remove(stored)
    
    assert client.post(f"/api/evidence/{ev_id}/detect-format").status_code == 404

def test_unknown_content(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 3)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"abc")
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    resp = client.post(f"/api/evidence/{ev_id}/detect-format")
    assert resp.status_code == 200
    data = resp.json()
    assert data["format_detection"]["detected_format"] == "UNKNOWN"

def test_large_file(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 10000)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00"*9984)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    resp = client.post(f"/api/evidence/{ev_id}/detect-format")
    assert resp.status_code == 200
    assert resp.json()["format_detection"]["detected_format"] == "MP4_ISO_BMFF"

def test_no_path_leakage(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    import json
    data = json.dumps(client.post(f"/api/evidence/{ev_id}/detect-format").json())
    assert "stored_path" not in data
    assert "data/raw" not in data

def test_evil_filename_isolation(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "../../evil.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("../../evil.mp4", f)})
        
    resp = client.post(f"/api/evidence/{ev_id}/detect-format")
    assert resp.status_code == 200
    assert resp.json()["format_detection"]["detected_format"] == "MP4_ISO_BMFF"
