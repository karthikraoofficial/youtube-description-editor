import threading
from concurrent.futures import ThreadPoolExecutor

from app.youtube.errors import GatewayError
from app.youtube.fake import FakeGateway, FakeGatewayProvider

from .conftest import CLIENT_HEADERS, make_client


def connect(client):
    return client.post("/api/auth/connect", headers=CLIENT_HEADERS)


def test_missing_client_secret_is_reported_and_connect_refused(settings):
    provider = FakeGatewayProvider(FakeGateway(), has_client_secret=False)
    with make_client(settings, provider) as c:
        assert c.get("/api/auth/status").json() == {"state": "no_client_secret", "channel": None}
        r = connect(c)
    assert r.status_code == 409
    assert provider.connected is False


def test_starts_disconnected_without_a_token(client):
    assert client.get("/api/auth/status").json() == {"state": "disconnected", "channel": None}


def test_connect_shows_the_channel(client):
    r = connect(client)
    assert r.status_code == 200
    assert r.json() == {
        "state": "connected",
        "channel": {"id": "UC_fake_channel", "title": "Fake Channel", "avatar_url": None},
    }
    assert client.get("/api/auth/status").json()["state"] == "connected"


def test_cached_token_reconnects_on_restart_without_spending_quota(settings, provider, gateway):
    with make_client(settings, provider) as c:
        connect(c)
    calls_after_connect = len(gateway.calls)

    with make_client(settings, provider) as c:
        status = c.get("/api/auth/status").json()

    assert status["state"] == "connected"
    assert status["channel"]["title"] == "Fake Channel"
    assert len(gateway.calls) == calls_after_connect


def test_expired_token_asks_to_reconnect(settings, provider):
    with make_client(settings, provider) as c:
        connect(c)
    provider.expire()

    with make_client(settings, provider) as c:
        assert c.get("/api/auth/status").json() == {"state": "expired", "channel": None}
        assert connect(c).json()["state"] == "connected"


def test_disconnect_revokes_and_forgets_the_token(settings, provider):
    with make_client(settings, provider) as c:
        connect(c)
        r = c.post("/api/auth/disconnect", headers=CLIENT_HEADERS)
        assert r.json() == {"state": "disconnected", "channel": None}
    assert provider.revoked is True

    with make_client(settings, provider) as c:
        assert c.get("/api/auth/status").json()["state"] == "disconnected"


def test_startup_survives_youtube_being_unreachable(settings, provider, gateway):
    provider.connected = True  # a cached token exists, but the Channel isn't in the store yet
    gateway.fail_with = GatewayError("YouTube API error 503: backendError")

    with make_client(settings, provider) as c:
        assert c.get("/api/health").status_code == 200
        r = c.get("/api/auth/status")
        assert r.status_code == 502
        assert "503" in r.json()["detail"]

        gateway.fail_with = None
        assert c.get("/api/auth/status").json()["state"] == "connected"


def test_channel_lookup_failing_after_sign_in_forgets_the_token(client, provider, gateway):
    gateway.fail_with = GatewayError("This Google account has no YouTube channel.")
    r = connect(client)
    assert r.status_code == 502
    assert "no YouTube channel" in r.json()["detail"]
    assert provider.revoked is True
    assert client.get("/api/auth/status").json()["state"] == "disconnected"


def test_second_sign_in_while_one_is_pending_is_refused(settings):
    release = threading.Event()
    provider = FakeGatewayProvider(FakeGateway(), block_until=release)
    with make_client(settings, provider) as c:
        with ThreadPoolExecutor(1) as pool:
            first = pool.submit(connect, c)
            assert provider.flow_started.wait(5)
            second = connect(c)
            assert c.get("/api/auth/status").json()["state"] == "disconnected"  # status isn't blocked
            release.set()
            assert first.result(5).json()["state"] == "connected"
    assert second.status_code == 409


def test_google_error_during_connect_is_reported_without_crashing(settings):
    provider = FakeGatewayProvider(FakeGateway(), connect_error="access_denied")
    with make_client(settings, provider) as c:
        r = connect(c)
        assert r.status_code == 502
        assert "access_denied" in r.json()["detail"]
        assert c.get("/api/auth/status").json()["state"] == "disconnected"
