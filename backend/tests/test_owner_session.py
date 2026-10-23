"""Only the Owner gets in: the allowlisted Google account, then a signed session cookie (ADR-0019)."""
import dataclasses

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.main import create_app
from app.shorts import FakeShortsProber

from .conftest import CLIENT_HEADERS, sign_in

OWNER = "owner@example.com"
HTTPS = "https://127.0.0.1"  # Secure cookies are only sent over https


@pytest.fixture
def cloud_settings(settings):
    return dataclasses.replace(settings, owner_email=OWNER, session_secret="s" * 32,
                               token_key=Fernet.generate_key().decode(), public_url=HTTPS)


@pytest.fixture
def cloud(cloud_settings, provider, clock):
    app = create_app(cloud_settings, provider=provider, prober=FakeShortsProber(default=False), clock=clock)
    with TestClient(app, base_url=HTTPS) as c:
        yield c


def test_without_a_session_every_api_route_is_refused(cloud):
    assert cloud.get("/api/videos").status_code == 401
    assert cloud.get("/api/auth/status").status_code == 401
    assert cloud.post("/api/sync", headers=CLIENT_HEADERS).status_code == 401
    assert cloud.get("/api/health").status_code == 200
    assert cloud.get("/api/auth/login", follow_redirects=False).status_code == 302


def test_the_owner_signs_in_and_gets_a_session(cloud, provider):
    provider.email = OWNER.upper()  # Google may vary the case
    r = sign_in(cloud)
    assert r.headers["location"] == "/"
    cookie = r.headers["set-cookie"]
    assert "yde_session=" in cookie and "HttpOnly" in cookie and "Secure" in cookie and "samesite=lax" in cookie.lower()
    assert cloud.get("/api/auth/status").json()["state"] == "connected"
    assert cloud.get("/api/videos").status_code == 200


def test_any_other_account_is_refused_and_leaves_nothing_behind(cloud, provider):
    provider.email = "someone@else.com"
    r = sign_in(cloud)
    assert r.headers["location"] == "/?signin_error=not_allowed"
    assert "yde_session" not in r.headers.get("set-cookie", "")
    assert provider.revoked is True  # Google's grant to the stranger is withdrawn too
    assert cloud.get("/api/videos").status_code == 401
    with cloud.app.state.store.tx() as conn:
        assert conn.execute("SELECT COUNT(*) FROM channel").fetchone()[0] == 0
    assert cloud.app.state.store.get_setting("google_credentials") is None


def test_an_unverified_email_is_refused_even_if_it_matches(cloud, provider):
    provider.email, provider.email_verified = OWNER, False
    assert sign_in(cloud).headers["location"] == "/?signin_error=not_allowed"


def test_a_forged_or_expired_session_is_refused(cloud, clock):
    sign_in(cloud)
    assert cloud.get("/api/videos").status_code == 200

    real = cloud.cookies.get("yde_session")
    forged = real[:-2] + ("A" if real[-2] != "A" else "B") + real[-1]
    cloud.cookies.clear()
    assert cloud.get("/api/videos", cookies={"yde_session": forged}).status_code == 401
    assert cloud.get("/api/videos", cookies={"yde_session": real}).status_code == 200

    clock.advance(31 * 24 * 3600)
    assert cloud.get("/api/videos", cookies={"yde_session": real}).status_code == 401


def test_disconnect_ends_the_session(cloud):
    sign_in(cloud)
    cloud.post("/api/auth/disconnect", headers=CLIENT_HEADERS)
    assert cloud.get("/api/videos").status_code == 401


def test_the_stored_google_token_is_encrypted(cloud, provider):
    sign_in(cloud)
    stored = cloud.app.state.store.get_setting("google_credentials")
    assert provider.credentials_json not in stored
    assert "refresh" not in stored


def test_a_session_secret_without_an_owner_is_refused_at_startup(settings, provider):
    with pytest.raises(ValueError, match="YDE_OWNER_EMAIL"):
        create_app(dataclasses.replace(settings, session_secret="s" * 32), provider=provider)


def test_the_sign_in_settings_come_from_the_environment(monkeypatch, tmp_path):
    from app.main import settings_from_env

    monkeypatch.setenv("YDE_PUBLIC_URL", "https://yde.example.app")
    monkeypatch.setenv("YDE_OWNER_EMAIL", OWNER)
    monkeypatch.setenv("YDE_SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("YDE_TOKEN_KEY", "k" * 44)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "abc.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "not-a-real-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example/yde")
    monkeypatch.setenv("BLOB_STORE_ID", "store_abc")
    s = settings_from_env()
    assert (s.public_url, s.owner_email, s.session_secret, s.token_key, s.google_client_id, s.google_client_secret) == (
        "https://yde.example.app", OWNER, "s" * 32, "k" * 44, "abc.apps.googleusercontent.com", "not-a-real-secret")
    assert "s" * 32 not in repr(s) and "not-a-real-secret" not in repr(s)


def test_disconnect_also_ends_copies_of_the_session_cookie(cloud):
    sign_in(cloud)
    copied = cloud.cookies.get("yde_session")  # e.g. left in another browser
    cloud.post("/api/auth/disconnect", headers=CLIENT_HEADERS)
    cloud.cookies.clear()
    assert cloud.get("/api/videos", cookies={"yde_session": copied}).status_code == 401

    sign_in(cloud)  # a new sign-in gets a working session again
    assert cloud.get("/api/videos").status_code == 200


def test_odd_cookies_and_states_are_refused_not_crashed_on(cloud):
    from app import session

    # An HTTP client can't even send this cookie, so check the verifier itself.
    assert session.verify("s" * 32, "é.é.é.é", now=0, epoch=0) is None
    assert session.verify("s" * 32, "garbage", now=0, epoch=0) is None
    cloud.get("/api/auth/login", follow_redirects=False)
    r = cloud.get("/api/auth/callback?code=x&state=%C3%A9", follow_redirects=False)
    assert r.headers["location"] == "/?signin_error=state"


@pytest.mark.parametrize("change, missing", [
    (dict(token_key=None), "YDE_TOKEN_KEY"),
    (dict(public_url="http://yde.example.app"), "https"),
    (dict(session_secret=None), "YDE_SESSION_SECRET"),
])
def test_a_deployment_missing_a_safeguard_refuses_to_start(cloud_settings, provider, change, missing):
    deployed = dataclasses.replace(cloud_settings, public_url="https://yde.example.app")
    with pytest.raises(ValueError, match=missing):
        create_app(dataclasses.replace(deployed, **change), provider=provider)


def test_a_token_sealed_with_another_key_is_reported_and_treated_as_disconnected(cloud_settings, provider, clock, caplog):
    app = create_app(cloud_settings, provider=provider, prober=FakeShortsProber(default=False), clock=clock)
    with TestClient(app, base_url=HTTPS) as c:
        sign_in(c)
        old_token = c.app.state.store.get_setting("google_credentials")
    rekeyed = dataclasses.replace(cloud_settings, token_key=Fernet.generate_key().decode())
    with caplog.at_level("WARNING"):
        app = create_app(rekeyed, provider=provider, prober=FakeShortsProber(default=False), clock=clock)
        with TestClient(app, base_url=HTTPS) as c:
            sign_in(c)  # a session again; the stored token is checked only when the Connection is used
            caplog.clear()
            with c.app.state.store.tx() as conn:  # put back the token sealed under the old key
                conn.execute("UPDATE settings SET value = ? WHERE key = 'google_credentials'", (old_token,))
            assert c.get("/api/auth/status").json()["state"] == "disconnected"
    assert any("can't be read" in r.message for r in caplog.records)


BRAND = "pseudo-rush-mus-0000@pages.plusgoogle.com"


def test_a_brand_account_owner_gets_in_even_without_the_verified_flag(cloud_settings, provider, clock):
    """A Brand Account channel signs in as a Google-issued @pages.plusgoogle.com identity, which may not carry
    email_verified. Only Google issues those addresses, so the signed ID token is proof enough."""
    owner_is_brand = dataclasses.replace(cloud_settings, owner_email=BRAND)
    app = create_app(owner_is_brand, provider=provider, prober=FakeShortsProber(default=False), clock=clock)
    with TestClient(app, base_url=HTTPS) as c:
        provider.email, provider.email_verified = BRAND, False
        assert sign_in(c).headers["location"] == "/"
        assert c.get("/api/videos").status_code == 200


def test_an_unverified_lookalike_of_another_domain_is_still_refused(cloud, provider):
    provider.email, provider.email_verified = "pseudo@pages.plusgoogle.com.evil.example", False
    assert sign_in(cloud).headers["location"] == "/?signin_error=not_allowed"


def test_a_refusal_tells_only_this_browser_which_account_google_reported(cloud, provider, caplog):
    provider.email = "someone@else.com"
    with caplog.at_level("DEBUG"):
        r = sign_in(cloud)
    assert r.headers["location"] == "/?signin_error=not_allowed"  # not in the URL, so not in access logs
    cookie = next(h for h in r.headers.get_list("set-cookie") if h.startswith("yde_refused_account="))
    assert "someone@else.com" in cookie.replace("%40", "@") and "Max-Age=120" in cookie and "Secure" in cookie
    assert "someone@else.com" not in caplog.text
