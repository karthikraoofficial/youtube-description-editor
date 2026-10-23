"""Owner sign-in: Google's web flow, the Channel Connection, and Disconnect, through the HTTP seam (ADR-0019)."""
from urllib.parse import parse_qs, urlparse

from app.youtube.errors import GatewayError
from app.youtube.fake import FakeGateway, FakeGatewayProvider

from .conftest import CLIENT_HEADERS, make_client, sign_in


def status(client):
    return client.get("/api/auth/status").json()


def test_missing_client_secret_is_reported_and_sign_in_goes_nowhere(settings):
    provider = FakeGatewayProvider(FakeGateway(), has_client_secret=False)
    with make_client(settings, provider) as c:
        assert status(c) == {"state": "no_client_secret", "channel": None}
        r = c.get("/api/auth/login", follow_redirects=False)
    assert r.headers["location"] == "/?signin_error=no_client_secret"
    assert provider.exchanged == []


def test_starts_disconnected_without_a_token(client):
    assert status(client) == {"state": "disconnected", "channel": None}


def test_sign_in_sends_the_browser_to_google_and_back_to_the_apps_callback(client):
    r = client.get("/api/auth/login", follow_redirects=False)
    assert r.status_code == 302
    url = urlparse(r.headers["location"])  # the fake consents at once, so it points straight at the callback
    assert f"{url.scheme}://{url.netloc}{url.path}" == "http://localhost:5173/api/auth/callback"
    assert parse_qs(url.query)["state"][0]


def test_the_callback_connects_the_channel_and_returns_to_the_app(client):
    r = sign_in(client)
    assert (r.status_code, r.headers["location"]) == (302, "/")
    assert status(client) == {
        "state": "connected",
        "channel": {"id": "UC_fake_channel", "title": "Fake Channel", "avatar_url": None},
    }


def test_a_callback_whose_state_does_not_match_is_refused(client, provider):
    client.get("/api/auth/login", follow_redirects=False)
    r = client.get("/api/auth/callback?code=fake-code&state=forged", follow_redirects=False)
    assert r.headers["location"] == "/?signin_error=state"
    assert provider.exchanged == []
    assert status(client)["state"] == "disconnected"


def test_cancelling_on_googles_consent_page_comes_back_with_a_clear_error(client, provider):
    login = client.get("/api/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    r = client.get(f"/api/auth/callback?error=access_denied&state={state}", follow_redirects=False)
    assert r.headers["location"] == "/?signin_error=access_denied"
    assert status(client)["state"] == "disconnected"


def test_the_sign_in_survives_a_restart_without_spending_quota(settings, provider, gateway):
    with make_client(settings, provider) as c:
        sign_in(c)
    calls_after_sign_in = len(gateway.calls)

    with make_client(settings, provider) as c:
        assert status(c)["channel"]["title"] == "Fake Channel"
    assert len(gateway.calls) == calls_after_sign_in


def test_an_expired_sign_in_asks_to_sign_in_again(settings, provider):
    with make_client(settings, provider) as c:
        sign_in(c)
    provider.expire()

    with make_client(settings, provider) as c:
        assert status(c) == {"state": "expired", "channel": None}
        sign_in(c)
        assert status(c)["state"] == "connected"


def test_disconnect_revokes_and_forgets_the_token(settings, provider):
    with make_client(settings, provider) as c:
        sign_in(c)
        r = c.post("/api/auth/disconnect", headers=CLIENT_HEADERS)
        assert r.json() == {"state": "disconnected", "channel": None}
    assert provider.revoked is True

    with make_client(settings, provider) as c:
        assert status(c)["state"] == "disconnected"


def test_startup_survives_youtube_being_unreachable(settings, provider, gateway):
    with make_client(settings, provider) as c:
        sign_in(c)
        with c.app.state.store.tx() as conn:
            conn.execute("DELETE FROM channel")  # a stored sign-in, but the Channel isn't known yet
    gateway.fail_with = GatewayError("YouTube API error 503: backendError")

    with make_client(settings, provider) as c:
        assert c.get("/api/health").status_code == 200
        r = c.get("/api/auth/status")
        assert r.status_code == 502
        assert "503" in r.json()["detail"]

        gateway.fail_with = None
        assert status(c)["state"] == "connected"


def test_an_account_without_a_channel_is_refused_and_its_token_forgotten(client, provider, gateway):
    gateway.fail_with = GatewayError("This Google account has no YouTube channel.")
    r = sign_in(client)
    assert r.headers["location"] == "/?signin_error=channel"
    assert provider.revoked is True
    gateway.fail_with = None
    assert status(client)["state"] == "disconnected"
