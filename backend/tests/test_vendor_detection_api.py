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
    test_file.write_bytes(b"IMKH" + b"\x00"*1020)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    resp = client.post(f"/api/evidence/{ev_id}/detect-vendor")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vendor_detection"]["vendor"] == "HIKVISION"
    assert data["status"] == "INGESTED"

def test_read_only_proof(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH" + b"\x00"*1020)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    client.post(f"/api/evidence/{ev_id}/hash")
    
    verify_resp1 = client.post(f"/api/evidence/{ev_id}/verify")
    hash1 = verify_resp1.json()["baseline_sha256"]
    
    # Run vendor detection
    client.post(f"/api/evidence/{ev_id}/detect-vendor")
    
    verify_resp2 = client.post(f"/api/evidence/{ev_id}/verify")
    assert verify_resp2.json()["match"] is True
    assert verify_resp2.json()["baseline_sha256"] == hash1
    
    assert client.get(f"/api/evidence/{ev_id}").json()["status"] == "HASHED"

def test_no_format_detection_required(client, tmp_path):
    # runs on a file whose format is UNKNOWN, without detect-format being called first
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH" + b"\x00"*1020)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    resp = client.post(f"/api/evidence/{ev_id}/detect-vendor")
    assert resp.status_code == 200
    assert resp.json()["vendor_detection"]["vendor"] == "HIKVISION"
    # Format detection was not run
    assert resp.json()["format_detection"] is None

def test_format_detection_preserved(client, tmp_path):
    # if detect-format ran first, its format_detection result is identical after vendor detection
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    r1 = client.post(f"/api/evidence/{ev_id}/detect-format").json()
    r2 = client.post(f"/api/evidence/{ev_id}/detect-vendor").json()
    
    assert r1["format_detection"] == r2["format_detection"]

def test_detect_twice(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH" + b"\x00"*1020)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    r1 = client.post(f"/api/evidence/{ev_id}/detect-vendor").json()
    r2 = client.post(f"/api/evidence/{ev_id}/detect-vendor").json()
    assert r1["vendor_detection"]["vendor"] == r2["vendor_detection"]["vendor"]
    assert r1["vendor_detection"]["detected_at"] != r2["vendor_detection"]["detected_at"]

def test_registered_item(client):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    assert client.post(f"/api/evidence/{ev_id}/detect-vendor").status_code == 409

def test_unknown_id(client):
    assert client.post("/api/evidence/nonexistent/detect-vendor").status_code == 404

def test_missing_file(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH" + b"\x00"*1020)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    stored = tmp_path / "raw" / case_id / ev_id
    os.chmod(stored, stat.S_IWRITE)
    os.remove(stored)
    
    assert client.post(f"/api/evidence/{ev_id}/detect-vendor").status_code == 404

def test_no_path_leakage(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH" + b"\x00"*1020)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    import json
    data = json.dumps(client.post(f"/api/evidence/{ev_id}/detect-vendor").json())
    assert "stored_path" not in data
    assert "data/raw" not in data

def test_evil_filename_isolation(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "../../evil.dav", 1024)
    test_file = tmp_path / "vid.dav"
    test_file.write_bytes(b"DHAV" + b"\x00"*1020)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("../../evil.dav", f)})
        
    resp = client.post(f"/api/evidence/{ev_id}/detect-vendor")
    assert resp.status_code == 200
    assert resp.json()["vendor_detection"]["vendor"] == "DAHUA"
    
    # Ensure it's stored where it should be
    stored = tmp_path / "raw" / case_id / ev_id
    assert stored.exists()

import hashlib
def compute_file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def test_vendor_detection_changes_only_vendor_detection(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    client.post(f"/api/evidence/{ev_id}/hash")
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    before_resp = client.get(f"/api/evidence/{ev_id}")
    before_data = before_resp.json()
    
    stored_path = tmp_path / "raw" / case_id / ev_id
    before_sha256 = compute_file_sha256(stored_path)
    before_size = stored_path.stat().st_size
    
    client.post(f"/api/evidence/{ev_id}/detect-vendor")
    
    after_resp = client.get(f"/api/evidence/{ev_id}")
    after_data = after_resp.json()
    
    after_sha256 = compute_file_sha256(stored_path)
    after_size = stored_path.stat().st_size
    
    assert before_sha256 == after_sha256
    assert before_size == after_size
    
    after_vendor = after_data.pop("vendor_detection")
    before_vendor = before_data.pop("vendor_detection")
    
    assert before_vendor is None
    assert after_vendor["vendor"] == "HIKVISION"
    assert before_data == after_data
    
    assert before_data["format_detection"] is not None
    assert after_data["format_detection"] == before_data["format_detection"]
    
    verify_resp = client.post(f"/api/evidence/{ev_id}/verify")
    assert verify_resp.json()["match"] is True

def test_vendor_detection_changes_only_vendor_detection_ingested(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"IMKH\x00\x00\x00\x1cftypisom" + b"\x00"*1012)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
        
    before_resp = client.get(f"/api/evidence/{ev_id}")
    before_data = before_resp.json()
    
    stored_path = tmp_path / "raw" / case_id / ev_id
        
    before_sha256 = compute_file_sha256(stored_path)
    before_size = stored_path.stat().st_size
    
    client.post(f"/api/evidence/{ev_id}/detect-vendor")
    
    after_resp = client.get(f"/api/evidence/{ev_id}")
    after_data = after_resp.json()
    
    after_sha256 = compute_file_sha256(stored_path)
    after_size = stored_path.stat().st_size
    
    assert before_sha256 == after_sha256
    assert before_size == after_size
    
    after_vendor = after_data.pop("vendor_detection")
    before_vendor = before_data.pop("vendor_detection")
    
    assert before_vendor is None
    assert after_vendor["vendor"] == "HIKVISION"
    assert before_data == after_data
