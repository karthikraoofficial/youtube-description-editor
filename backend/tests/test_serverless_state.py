"""Every request may land on a different, fresh instance of the app (ADR-0020): nothing that matters lives
only in one instance's memory."""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, settings_from_env
from app.shorts import FakeShortsProber
from app.youtube.errors import AuthExpired
from app.youtube.fake import sample_videos

from .conftest import CLIENT_HEADERS, TEST_DATABASE_URL, FakeClock, make_client, sign_in


def status(client):
    return client.get("/api/auth/status").json()["state"]


def test_two_running_instances_agree_on_the_connection(settings, provider):
    with make_client(settings, provider) as a, make_client(settings, provider) as b:
        assert status(b) == "disconnected"
        sign_in(a)
        assert status(b) == "connected"  # b started before the sign-in, and still sees it

        a.post("/api/auth/disconnect", headers=CLIENT_HEADERS)
        assert status(b) == "disconnected"


def test_an_expiry_one_instance_meets_is_seen_by_the_others(settings, provider, gateway):
    gateway.videos = sample_videos()
    with make_client(settings, provider) as a, make_client(settings, provider) as b:
        sign_in(a)
        gateway.fail_with = AuthExpired("Google sign-in expired")
        assert a.post("/api/sync", headers=CLIENT_HEADERS).status_code == 401
        gateway.fail_with = None
        assert status(b) == "expired"

        sign_in(b)  # signing in again clears it everywhere
        assert status(a) == "connected"


def test_a_sync_running_on_another_instance_is_refused(settings, provider, gateway, clock):
    gateway.videos = sample_videos()
    with make_client(settings, provider, clock=clock) as a, make_client(settings, provider, clock=clock) as b:
        sign_in(a)
        assert b.app.state.store.acquire_lease("sync", now=clock(), seconds=300) is not None  # b is mid-Sync
        r = a.post("/api/sync", headers=CLIENT_HEADERS)
        assert (r.status_code, r.json()["detail"]) == (409, "A sync is already running.")


def test_a_sync_lease_left_by_a_crashed_instance_runs_out(settings, provider, gateway, clock):
    gateway.videos = sample_videos()
    with make_client(settings, provider, clock=clock) as a:
        sign_in(a)
        a.app.state.store.acquire_lease("sync", now=clock(), seconds=300)  # and then that instance died
        clock.advance(301)
        assert a.post("/api/sync", headers=CLIENT_HEADERS).status_code == 200
        assert a.post("/api/sync", headers=CLIENT_HEADERS).status_code == 200  # released after each Sync


DEPLOYED_ENV = {
    "YDE_PUBLIC_URL": "https://yde.example.app", "YDE_OWNER_EMAIL": "owner@example.com",
    "YDE_SESSION_SECRET": "s" * 32, "YDE_TOKEN_KEY": "k" * 44,
    "DATABASE_URL": "postgresql://u:p@db.example/yde", "BLOB_READ_WRITE_TOKEN": "vercel_blob_rw_" + "x" * 20,
}


def test_a_deployment_takes_its_host_and_origin_from_the_public_url(monkeypatch):
    for name, value in DEPLOYED_ENV.items():
        monkeypatch.setenv(name, value)
    s = settings_from_env()
    assert s.allowed_hosts == ("yde.example.app",)
    assert s.frontend_origin == "https://yde.example.app"


@pytest.mark.parametrize("unset", ["DATABASE_URL", "BLOB_READ_WRITE_TOKEN"])
def test_a_deployment_without_lasting_storage_refuses_to_start(monkeypatch, unset):
    for name, value in DEPLOYED_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(unset)
    with pytest.raises(ValueError, match="DATABASE_URL" if unset == "DATABASE_URL" else "Blob"):
        settings_from_env()


def test_local_mode_keeps_its_loopback_host_check(settings, provider):
    with make_client(settings, provider) as c:
        assert c.get("/api/health", headers={"host": "evil.example"}).status_code == 400
        assert c.get("/api/health", headers={"host": "localhost:8000"}).status_code == 200


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="set YDE_TEST_DATABASE_URL to run on Postgres")
def test_a_deployment_writes_nothing_to_the_filesystem(tmp_path, provider):
    data_dir = tmp_path / "read-only-in-the-cloud"
    deployed = Settings(
        data_dir=data_dir, database_url=TEST_DATABASE_URL, blob_backups=True, public_url="https://127.0.0.1",
        owner_email="owner@example.com", session_secret="s" * 32,
        token_key="wO8kMmTx1sXbqzFhUTcVqQ1g7m5QBH6P0Jj3PbG6jHo=", allowed_hosts=("127.0.0.1",))
    app = create_app(deployed, provider=provider, prober=FakeShortsProber(default=False), clock=FakeClock())
    with TestClient(app, base_url="https://127.0.0.1") as c:
        assert c.get("/api/health").status_code == 200
    assert not data_dir.exists()


def test_channel_quota_and_runs_are_the_same_on_every_instance(settings, provider, gateway):
    from app.youtube.fake import fake_video

    from .conftest import drive

    gateway.videos = [fake_video("a", description="Song")]
    with make_client(settings, provider) as a, make_client(settings, provider) as b:
        sign_in(a)
        a.post("/api/sync", headers=CLIENT_HEADERS)
        cs = a.post("/api/changesets", json={"operation": {"type": "append", "text": "Footer"}, "video_ids": ["a"]},
                    headers=CLIENT_HEADERS).json()
        run_id = a.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": 1},
                        headers=CLIENT_HEADERS).json()["id"]
        drive(a, run_id)

        assert b.get("/api/auth/status").json()["channel"]["title"] == "Fake Channel"
        assert b.get("/api/quota").json() == a.get("/api/quota").json()
        assert b.get("/api/quota").json()["used"] > 0
        assert [(r["id"], r["status"]) for r in b.get("/api/runs").json()] == [(run_id, "completed")]


def test_two_real_syncs_on_two_instances_never_overlap(settings, provider, gateway):
    gateway.videos = sample_videos()
    with make_client(settings, provider) as a, make_client(settings, provider) as b:
        sign_in(a)
        overlapping = []
        real_list = gateway.list_uploads_page

        def list_while_b_tries_to_sync(*args):
            if not overlapping:
                overlapping.append(b.post("/api/sync", headers=CLIENT_HEADERS).status_code)
            return real_list(*args)

        gateway.list_uploads_page = list_while_b_tries_to_sync
        assert a.post("/api/sync", headers=CLIENT_HEADERS).status_code == 200
    assert overlapping == [409]


def test_a_sync_that_outlived_its_lease_does_not_release_the_next_ones(settings, provider, gateway, clock):
    store = make_client(settings, provider, clock=clock).app.state.store
    first = store.acquire_lease("sync", now=clock(), seconds=300)
    clock.advance(301)
    second = store.acquire_lease("sync", now=clock(), seconds=300)
    assert first and second and first != second
    store.release_lease("sync", first)  # the first Sync finally ends
    assert store.acquire_lease("sync", now=clock(), seconds=300) is None  # the second still holds it


def test_an_expiry_from_an_old_sign_in_does_not_expire_a_newer_one(settings, provider, gateway):
    with make_client(settings, provider) as c:
        sign_in(c)
        connection = c.app.state.connection
        old_gateway = connection.gateway()  # e.g. held by a Run Step in another tab
        sign_in(c)  # signed in again with new credentials

        gateway.fail_with = AuthExpired("Google sign-in expired")
        with pytest.raises(AuthExpired):
            old_gateway.get_my_channel()  # Google refuses the old token
        gateway.fail_with = None
        assert status(c) == "connected"

        gateway.fail_with = AuthExpired("Google sign-in expired")
        with pytest.raises(AuthExpired):
            connection.gateway().get_my_channel()  # now the current one
        gateway.fail_with = None
        assert status(c) == "expired"


def test_a_token_refresh_never_brings_back_credentials_after_a_disconnect(settings, provider):
    with make_client(settings, provider) as c:
        sign_in(c)
        store, connection = c.app.state.store, c.app.state.connection
        stale = store.get_setting("google_credentials")
        c.post("/api/auth/disconnect", headers=CLIENT_HEADERS)
        assert store.replace_setting("google_credentials", stale, "plain:{}") is False  # the refresh lost the race
        assert store.get_setting("google_credentials") is None
