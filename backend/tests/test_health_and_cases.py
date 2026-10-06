def test_health_check(client):
    """Proves root and health endpoints return 200."""
    assert client.get("/").status_code == 200
    assert client.get("/api/health").status_code == 200

def test_create_and_get_case(client):
    """Proves case creation and retrieval work."""
    response = client.post("/api/cases", json={"case_name": "Test Case"})
    assert response.status_code == 201
    case_id = response.json()["case_id"]
    
    # Get by ID
    assert client.get(f"/api/cases/{case_id}").status_code == 200
    
    # List all
    list_resp = client.get("/api/cases")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

def test_list_multiple_cases(client):
    client.post("/api/cases", json={"case_name": "Case 1"})
    client.post("/api/cases", json={"case_name": "Case 2"})
    client.post("/api/cases", json={"case_name": "Case 3"})
    list_resp = client.get("/api/cases")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 3

def test_unknown_case(client):
    """Proves getting an unknown case returns 404."""
    assert client.get("/api/cases/nonexistent").status_code == 404
