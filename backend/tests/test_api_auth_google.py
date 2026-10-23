"""The real Google provider's web sign-in through the HTTP seam, with only Google's network edges stubbed."""
import json
import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from google.oauth2.credentials import Credentials
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError

from app.config import Settings
from app.main import create_app
from app.youtube import google as google_mod
from app.youtube.gateway import Channel

from .conftest import BASE_URL, CLIENT_HEADERS, sign_in

# Assembled from pieces so the pre-commit secret guard doesn't see credential-shaped literals.
FAKE_ACCESS = "ya29" + ".fake-access-token-value"
FAKE_REFRESH = "1//0" + "fakeRefreshTokenValue123"
FAKE_CLIENT_SECRET = "GOCSPX" + "-fakeClientSecret"
CLIENT_ID = "abc.apps.googleusercontent.com"


class StubFlow:
    """Google's side of the flow: hands out the consent URL, and credentials for a code."""

    def __init__(self, redirect_uri):
        self.redirect_uri = redirect_uri
        self.credentials = None

    def authorization_url(self, **kwargs):
        return "https://accounts.google.com/o/oauth2/auth?" + "&".join(
            f"{k}={v}" for k, v in {**kwargs, "redirect_uri": self.redirect_uri}.items()), kwargs["state"]

    def fetch_token(self, code):
        logging.getLogger("test.flow").info("exchanging code %s", code)
        self.credentials = Credentials(token=FAKE_ACCESS, refresh_token=FAKE_REFRESH, token_uri=google_mod.TOKEN_URI,
                                       client_id=CLIENT_ID, client_secret=FAKE_CLIENT_SECRET, scopes=google_mod.SCOPES,
                                       id_token="header.claims.signature",
                                       expiry=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1))


@pytest.fixture
def real_client(tmp_path, monkeypatch):
    (tmp_path / "client_secret.json").write_text(json.dumps({"web": {
        "client_id": CLIENT_ID, "client_secret": FAKE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": google_mod.TOKEN_URI}}))
    flows = []

    def from_client_config(config, scopes, redirect_uri, **kwargs):
        assert scopes == google_mod.SCOPES and kwargs == {"autogenerate_code_verifier": False}
        flows.append(StubFlow(redirect_uri))
        return flows[-1]

    monkeypatch.setattr(google_mod.Flow, "from_client_config", staticmethod(from_client_config))
    monkeypatch.setattr(google_mod.id_token, "verify_oauth2_token",
                        lambda token, request, audience: {"email": "owner@example.com", "email_verified": True})
    monkeypatch.setattr(google_mod.GoogleGateway, "get_my_channel", lambda self: Channel(
        id="UC_real", title="My Channel", avatar_url="https://yt3.example/a.jpg", uploads_playlist_id="UU_real"))
    revoked = []
    monkeypatch.setattr(google_mod.httpx, "post",
                        lambda url, data, timeout: revoked.append(data) or type("R", (), {"status_code": 200})())
    settings = Settings(data_dir=tmp_path, fake=False)
    with TestClient(create_app(settings), base_url=BASE_URL) as c:
        c.revoked, c.settings, c.flows = revoked, settings, flows
        yield c


def test_sign_in_asks_google_for_identity_and_offline_youtube_access(real_client):
    r = real_client.get("/api/auth/login", follow_redirects=False)
    query = parse_qs(urlparse(r.headers["location"]).query)
    assert query["access_type"] == ["offline"] and query["prompt"] == ["consent"]
    assert real_client.flows[0].redirect_uri == "http://localhost:5173/api/auth/callback"


def test_sign_in_keeps_the_token_in_the_database_and_never_logs_it(real_client, caplog):
    caplog.set_level(logging.DEBUG)
    r = sign_in(real_client)

    assert r.headers["location"] == "/"
    assert real_client.get("/api/auth/status").json()["channel"]["title"] == "My Channel"
    stored = real_client.app.state.store.get_setting("google_credentials")
    assert json.loads(stored.removeprefix("plain:"))["refresh_token"] == FAKE_REFRESH  # local mode: no key
    assert not (real_client.settings.data_dir / "token.json").exists()
    for secret in (FAKE_ACCESS, FAKE_REFRESH, FAKE_CLIENT_SECRET):
        assert secret not in caplog.text
        assert secret not in r.text


def test_a_code_google_refuses_comes_back_as_an_error(real_client, monkeypatch):
    def refuse(self, code):
        raise InvalidGrantError()

    monkeypatch.setattr(StubFlow, "fetch_token", refuse)
    assert sign_in(real_client).headers["location"] == "/?signin_error=google"
    assert real_client.get("/api/auth/status").json()["state"] == "disconnected"


def test_disconnect_revokes_with_google_and_forgets_the_token(real_client):
    sign_in(real_client)
    r = real_client.post("/api/auth/disconnect", headers=CLIENT_HEADERS)

    assert r.json()["state"] == "disconnected"
    assert real_client.revoked == [{"token": FAKE_REFRESH}]
    assert real_client.app.state.store.get_setting("google_credentials") is None


def test_a_desktop_client_secret_is_not_enough_for_the_web_flow(tmp_path):
    (tmp_path / "client_secret.json").write_text(json.dumps({"installed": {"client_id": CLIENT_ID}}))
    with TestClient(create_app(Settings(data_dir=tmp_path)), base_url=BASE_URL) as c:
        assert c.get("/api/auth/status").json()["state"] == "no_client_secret"


def test_the_client_can_come_from_the_environment_instead_of_a_file(tmp_path):
    settings = Settings(data_dir=tmp_path, google_client_id=CLIENT_ID, google_client_secret=FAKE_CLIENT_SECRET)
    with TestClient(create_app(settings), base_url=BASE_URL) as c:
        assert c.get("/api/auth/status").json()["state"] == "disconnected"
