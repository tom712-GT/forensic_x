import os
import stat
import struct
from pathlib import Path
import pytest
from app.services.metadata_service import MetadataService
import builtins

def create_case(client):
    return client.post("/api/cases", json={"case_name": "Test Meta"}).json()["case_id"]

def register_evidence(client, case_id, filename="test.mp4", file_size=1024):
    return client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": filename,
        "evidence_type": "BIN",
        "file_size": file_size
    }).json()["evidence_id"]

def make_mp4(tmp_path, size=1024):
    test_file = tmp_path / "vid.mp4"
    # tiny MP4: ftyp + moov(mvhd)
    ftyp = struct.pack(">I4s4sI4s4s", 24, b"ftyp", b"isom", 0, b"isom", b"iso2")
    mvhd_data = b"\x00"*4 + struct.pack(">IIII", 3600, 3600, 1000, 5000) + b"\x00"*(108 - 8 - 4 - 16)
    mvhd = struct.pack(">I4s", 108, b"mvhd") + mvhd_data
    moov = struct.pack(">I4s", 8 + 108, b"moov") + mvhd
    mdat_size = size - len(ftyp) - len(moov)
    mdat = struct.pack(">I4s", mdat_size, b"mdat") + b"\x00"*(mdat_size - 8)
    test_file.write_bytes(ftyp + moov + mdat)
    return test_file

def make_avi(tmp_path, size=1024):
    test_file = tmp_path / "vid.avi"
    # RIFF AVI hdrl avih
    avih = b"avih" + struct.pack("<I", 56) + struct.pack("<IIIIIIIIIIIIII", 40000, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0)
    hdrl = b"LIST" + struct.pack("<I", 4 + len(avih)) + b"hdrl" + avih
    avi = b"RIFF" + struct.pack("<I", 4 + len(hdrl)) + b"AVI " + hdrl
    test_file.write_bytes(avi + b"\x00"*(size - len(avi)))
    return test_file

def test_1_mp4_happy_path(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = make_mp4(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    resp = client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert resp.status_code == 200
    data = resp.json()
    assert data["container"] == "MP4"
    assert any(f["field"] == "creation_time" and f["note"] == "Value stored in the container; not proof of when the recorded event happened." for f in data["result"]["fields"])
    
    import json
    resp_text = json.dumps(data)
    assert "stored_path" not in resp_text
    assert "\\\\" not in resp_text
    assert "D:" not in resp_text

def test_2_avi_happy_path(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.avi", 1024)
    test_file = make_avi(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.avi", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    resp = client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert resp.status_code == 200
    data = resp.json()
    assert data["container"] == "AVI"
    assert any(f["field"] == "frames_per_second" and f["raw_value"] == 40000 and f["interpreted_value"] == 25.0 for f in data["result"]["fields"])

def test_3_get_metadata(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = make_mp4(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    resp1 = client.get(f"/api/evidence/{ev_id}/metadata")
    assert resp1.status_code == 404
    assert "Metadata not extracted" in resp1.json()["detail"]
    
    post_resp = client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert post_resp.status_code == 200
    
    resp2 = client.get(f"/api/evidence/{ev_id}/metadata")
    assert resp2.status_code == 200
    assert resp2.json() == post_resp.json()

def test_4_post_twice(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = make_mp4(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    r1 = client.post(f"/api/evidence/{ev_id}/extract-metadata").json()
    r2 = client.post(f"/api/evidence/{ev_id}/extract-metadata").json()
    assert r1["metadata_id"] == r2["metadata_id"]

def test_5_unknown_evidence(client):
    assert client.post("/api/evidence/nonexistent/extract-metadata").status_code == 404
    assert client.get("/api/evidence/nonexistent/metadata").status_code == 404

def test_6_registered_evidence(client):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    resp = client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Evidence must be ingested before metadata extraction"

def test_7_ingested_but_no_format(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = make_mp4(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    
    resp = client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert resp.status_code == 409
    assert "Metadata extraction not applicable: run format detection first or format unsupported" in resp.json()["detail"]

def test_8_unsupported_format(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "img.jpg", 1024)
    test_file = tmp_path / "vid.jpg"
    test_file.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00"*1020)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("img.jpg", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    resp = client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Metadata extraction not applicable: run format detection first or format unsupported"
    
    resp2 = client.get(f"/api/evidence/{ev_id}/metadata")
    assert resp2.status_code == 404
    assert "Metadata not extracted" in resp2.json()["detail"]
    
    audits = client.get(f"/api/audit-log?evidence_id={ev_id}").json()
    extract_audits = [a for a in audits if a["action"] == "METADATA_EXTRACT"]
    assert len(extract_audits) > 0
    assert extract_audits[-1]["outcome"] == "REJECTED"
    assert extract_audits[-1]["details"]["reason"] == "FORMAT_NOT_SUPPORTED"

def test_9_corrupt_mp4(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = tmp_path / "vid.mp4"
    test_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00\x00\x00\x00\x00\x00\x00\x00isomiso2avc1mp41" + b"\x00\x00\x00\x10garb" + b"\x00"*1000)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    resp = client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] in ("PARSE_ERROR", "PARTIAL")

def test_10_no_changes_to_evidence(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = make_mp4(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    import hashlib
    stored = tmp_path / "raw" / case_id / ev_id
    before_bytes = stored.read_bytes()
    before_hash = hashlib.sha256(before_bytes).hexdigest()
    
    before = client.get(f"/api/evidence/{ev_id}").json()
    client.post(f"/api/evidence/{ev_id}/extract-metadata")
    after = client.get(f"/api/evidence/{ev_id}").json()
    assert before == after
    
    after_bytes = stored.read_bytes()
    assert before_bytes == after_bytes
    assert before_hash == hashlib.sha256(after_bytes).hexdigest()

def test_11_hashed_evidence(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = make_mp4(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id}/hash")
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    resp = client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert resp.status_code == 200
    assert client.post(f"/api/evidence/{ev_id}/verify").json()["match"] is True

def test_12_deleted_file(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = make_mp4(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    stored = tmp_path / "raw" / case_id / ev_id
    os.chmod(stored, stat.S_IWRITE)
    os.remove(stored)
    
    resp = client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert resp.status_code == 404
    assert "Stored evidence file missing" in resp.json()["detail"]
    import json
    assert "\\" not in json.dumps(resp.json())

def test_13_unexpected_error(client, tmp_path, monkeypatch):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = make_mp4(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    def boom(*args, **kwargs):
        raise RuntimeError("secret C:\\x")
    monkeypatch.setattr(MetadataService, "extract", boom)
    
    resp = client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert resp.status_code == 500
    assert "secret" not in resp.json()["detail"]

def test_14_audit_log(client, tmp_path):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = make_mp4(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    client.post(f"/api/evidence/{ev_id}/extract-metadata")
    
    audits = client.get(f"/api/audit-log?evidence_id={ev_id}").json()
    extract_audits = [a for a in audits if a["action"] == "METADATA_EXTRACT"]
    assert len(extract_audits) == 1
    assert extract_audits[0]["outcome"] == "SUCCESS"
    import json
    assert "\\" not in json.dumps(extract_audits[0]["details"])

def test_14b_audit_log_failures(client, tmp_path):
    client.post("/api/evidence/nonexistent/extract-metadata")
    audits = client.get("/api/audit-log?evidence_id=nonexistent").json()
    assert any(a["action"] == "METADATA_EXTRACT" and a["outcome"] == "NOT_FOUND" for a in audits)
    
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    client.post(f"/api/evidence/{ev_id}/extract-metadata")
    audits = client.get(f"/api/audit-log?evidence_id={ev_id}").json()
    rej = [a for a in audits if a["action"] == "METADATA_EXTRACT" and a["outcome"] == "REJECTED"]
    assert len(rej) > 0
    assert rej[-1]["details"]["reason"] == "NOT_INGESTED"
    
    import json
    for a in audits:
        if a["action"] == "METADATA_EXTRACT":
            d = json.dumps(a["details"])
            assert "video.mp4" not in d
            assert "\\\\" not in d

def test_15_read_only_proof(client, tmp_path, monkeypatch):
    case_id = create_case(client)
    ev_id = register_evidence(client, case_id, "video.mp4", 1024)
    test_file = make_mp4(tmp_path)
    with open(test_file, "rb") as f:
        client.post(f"/api/evidence/{ev_id}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id}/detect-format")
    
    import app.services.metadata_service as m_svc
    original_open = builtins.open
    open_modes = []
    
    def mocked_open(*args, **kwargs):
        mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
        if str(args[0]).endswith(ev_id):
            open_modes.append(mode)
        return original_open(*args, **kwargs)
        
    monkeypatch.setattr(m_svc.builtins, "open", mocked_open)
    
    client.post(f"/api/evidence/{ev_id}/extract-metadata")
    assert open_modes == ["rb"]

def test_16_container_cross_check(client, tmp_path):
    case_id = create_case(client)
    
    ev_id1 = register_evidence(client, case_id, "video.mp4", 1024)
    test_file1 = make_mp4(tmp_path)
    with open(test_file1, "rb") as f:
        client.post(f"/api/evidence/{ev_id1}/file", files={"file": ("vid.mp4", f)})
    client.post(f"/api/evidence/{ev_id1}/detect-format")
    resp1 = client.post(f"/api/evidence/{ev_id1}/extract-metadata")
    assert resp1.json()["container"] == "MP4"

    ev_id2 = register_evidence(client, case_id, "video.avi", 1024)
    test_file2 = make_avi(tmp_path)
    with open(test_file2, "rb") as f:
        client.post(f"/api/evidence/{ev_id2}/file", files={"file": ("vid.avi", f)})
    client.post(f"/api/evidence/{ev_id2}/detect-format")
    resp2 = client.post(f"/api/evidence/{ev_id2}/extract-metadata")
    assert resp2.json()["container"] == "AVI"
