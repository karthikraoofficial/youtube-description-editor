from fastapi.testclient import TestClient

from .conftest import CLIENT_HEADERS


def test_health_reports_ok_and_fake_mode(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "fake": True}


def _add_echo(app):
    @app.post("/api/echo")
    def echo():
        return {"echo": True}


def test_mutating_request_without_client_header_is_rejected(app, client):
    _add_echo(app)
    assert client.post("/api/echo").status_code == 403


def test_mutating_request_with_client_header_is_allowed(app, client):
    _add_echo(app)
    r = client.post("/api/echo", headers=CLIENT_HEADERS)
    assert r.status_code == 200
    assert r.json() == {"echo": True}


def test_cors_allows_only_the_frontend_origin(client):
    ok = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    evil = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in evil.headers


def test_request_with_a_foreign_host_is_rejected(app):
    # A DNS-rebinding page reaches 127.0.0.1 but sends its own hostname.
    with TestClient(app, base_url="http://evil.example") as c:
        assert c.get("/api/health").status_code == 400


def test_localhost_host_is_accepted(app):
    with TestClient(app, base_url="http://localhost:5173") as c:
        assert c.get("/api/health").status_code == 200
