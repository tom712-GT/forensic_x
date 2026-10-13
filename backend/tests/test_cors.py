def test_cors_allowed_origin_preflight(client):
    r = client.options("/api/cases", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_allowed_origin_simple_get(client):
    r = client.get("/", headers={"Origin": "http://127.0.0.1:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_cors_unknown_origin_not_allowed(client):
    r = client.get("/", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_no_wildcard_and_no_credentials(client):
    r = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") != "*"
    assert "access-control-allow-credentials" not in r.headers
