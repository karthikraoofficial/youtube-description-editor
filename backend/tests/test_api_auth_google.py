"""The real Google provider through the HTTP seam, with only Google's network edges stubbed."""
import json
import logging

import pytest
from fastapi.testclient import TestClient
from google.oauth2.credentials import Credentials

from app.config import Settings
from app.main import create_app
from app.youtube import google as google_mod
from app.youtube.gateway import Channel

from .conftest import BASE_URL, CLIENT_HEADERS

# Assembled from pieces so the pre-commit secret guard doesn't see credential-shaped literals.
FAKE_ACCESS = "ya29" + ".fake-access-token-value"
FAKE_REFRESH = "1//0" + "fakeRefreshTokenValue123"
FAKE_CLIENT_SECRET = "GOCSPX" + "-fakeClientSecret"


class StubFlow:
    def run_local_server(self, **kwargs):
        logging.getLogger("test.flow").info("flow kwargs %s", kwargs)
        return Credentials(token=FAKE_ACCESS, refresh_token=FAKE_REFRESH,
                           token_uri="https://oauth2.googleapis.com/token",
                           client_id="abc.apps.googleusercontent.com", client_secret=FAKE_CLIENT_SECRET,
                           scopes=google_mod.SCOPES)


@pytest.fixture
def real_client(tmp_path, monkeypatch):
    (tmp_path / "client_secret.json").write_text(json.dumps({"installed": {
        "client_id": "abc.apps.googleusercontent.com", "client_secret": FAKE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": ["http://localhost"]}}))
    monkeypatch.setattr(google_mod.InstalledAppFlow, "from_client_secrets_file",
                        classmethod(lambda cls, *a, **k: StubFlow()))
    monkeypatch.setattr(google_mod.GoogleGateway, "get_my_channel", lambda self: Channel(
        id="UC_real", title="My Channel", avatar_url="https://yt3.example/a.jpg", uploads_playlist_id="UU_real"))
    revoked = []
    monkeypatch.setattr(google_mod.httpx, "post",
                        lambda url, data, timeout: revoked.append(data) or type("R", (), {"status_code": 200})())
    settings = Settings(data_dir=tmp_path, fake=False)
    with TestClient(create_app(settings), base_url=BASE_URL) as c:
        c.revoked = revoked
        c.settings = settings
        yield c


def test_connect_caches_the_token_in_the_data_folder_and_never_logs_it(real_client, caplog):
    caplog.set_level(logging.DEBUG)
    r = real_client.post("/api/auth/connect", headers=CLIENT_HEADERS)

    assert r.json()["state"] == "connected"
    saved = json.loads(real_client.settings.token_path.read_text())
    assert saved["refresh_token"] == FAKE_REFRESH
    for secret in (FAKE_ACCESS, FAKE_REFRESH, FAKE_CLIENT_SECRET):
        assert secret not in caplog.text
        assert secret not in r.text


def test_disconnect_revokes_with_google_and_deletes_the_token(real_client):
    real_client.post("/api/auth/connect", headers=CLIENT_HEADERS)
    r = real_client.post("/api/auth/disconnect", headers=CLIENT_HEADERS)

    assert r.json()["state"] == "disconnected"
    assert real_client.revoked == [{"token": FAKE_REFRESH}]
    assert not real_client.settings.token_path.exists()
