def create_case(client):
    return client.post("/api/cases", json={"case_name": "Test"}).json()["case_id"]

def test_register_valid(client):
    """Proves valid registration returns 201 with status REGISTERED."""
    case_id = create_case(client)
    resp = client.post(f"/api/cases/{case_id}/evidence", json={
        "original_filename": "test.bin",
        "evidence_type": "BIN",
        "file_size": 100
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "REGISTERED"

def test_register_negative_size(client):
    """Proves negative file_size is rejected with 422."""
    case_id = create_case(client)
    resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "a", "evidence_type": "b", "file_size": -5})
    assert resp.status_code == 422

def test_register_zero_size(client):
    """Proves zero file_size is accepted."""
    case_id = create_case(client)
    resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "a", "evidence_type": "b", "file_size": 0})
    assert resp.status_code == 201

def test_register_empty_filename(client):
    """Proves empty original_filename is rejected."""
    case_id = create_case(client)
    resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "", "evidence_type": "b", "file_size": 10})
    assert resp.status_code == 422

def test_register_spaces_filename(client):
    """Proves spaces-only filename is rejected."""
    case_id = create_case(client)
    resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "   ", "evidence_type": "b", "file_size": 10})
    assert resp.status_code == 422

def test_register_empty_evidence_type(client):
    """Proves empty evidence_type is rejected."""
    case_id = create_case(client)
    resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "a", "evidence_type": "", "file_size": 10})
    assert resp.status_code == 422

def test_register_invalid_size_type(client):
    """Proves string file_size is rejected."""
    case_id = create_case(client)
    resp = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "a", "evidence_type": "b", "file_size": "abc"})
    assert resp.status_code == 422

def test_register_missing_filename(client):
    """Proves missing original_filename is rejected."""
    case_id = create_case(client)
    resp = client.post(f"/api/cases/{case_id}/evidence", json={"evidence_type": "b", "file_size": 10})
    assert resp.status_code == 422

def test_unknown_case(client):
    """Proves registering and listing on unknown case returns 404."""
    assert client.post("/api/cases/nonexistent/evidence", json={"original_filename": "a", "evidence_type": "b", "file_size": 10}).status_code == 404
    assert client.get("/api/cases/nonexistent/evidence").status_code == 404

def test_case_isolation(client):
    """Proves evidence of case A is not listed under case B."""
    case_a = create_case(client)
    case_b = create_case(client)
    client.post(f"/api/cases/{case_a}/evidence", json={"original_filename": "a", "evidence_type": "b", "file_size": 10})
    assert len(client.get(f"/api/cases/{case_a}/evidence").json()) == 1
    assert len(client.get(f"/api/cases/{case_b}/evidence").json()) == 0

def test_unknown_evidence(client):
    """Proves getting unknown evidence ID returns 404."""
    assert client.get("/api/evidence/nonexistent").status_code == 404

def test_rejected_not_stored(client):
    """Proves rejected requests are not stored."""
    case_id = create_case(client)
    client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "", "evidence_type": "b", "file_size": 10})
    assert len(client.get(f"/api/cases/{case_id}/evidence").json()) == 0
