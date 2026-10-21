from app.youtube.errors import AuthExpired, PlaylistNotFound
from app.youtube.fake import FakeGateway, FakeGatewayProvider, fake_video
from app.youtube.gateway import Channel

from .conftest import CLIENT_HEADERS, make_client


def connect(c):
    assert c.post("/api/auth/connect", headers=CLIENT_HEADERS).status_code == 200


def sync(c):
    return c.post("/api/sync", headers=CLIENT_HEADERS)


def test_sync_needs_a_connected_channel(client):
    r = sync(client)
    assert r.status_code == 409


def test_sync_caches_only_public_videos_newest_first(client, gateway):
    gateway.videos = [
        fake_video("v1", title="Old public", published_at="2024-01-01T10:00:00Z", duration_s=600),
        fake_video("v2", title="Unlisted", privacy_status="unlisted"),
        fake_video("v3", title="Private", privacy_status="private"),
        fake_video("v4", title="New public", published_at="2025-06-01T10:00:00Z", duration_s=45,
                   description="Hello\nworld"),
    ]
    connect(client)
    r = sync(client)

    assert r.status_code == 200
    assert r.json()["video_count"] == 2
    videos = client.get("/api/videos").json()
    assert [v["id"] for v in videos] == ["v4", "v1"]
    assert videos[0] == {
        "id": "v4", "title": "New public", "description": "Hello\nworld",
        "published_at": "2025-06-01T10:00:00Z", "duration_s": 45,
        "thumbnail_url": "https://i.ytimg.com/vi/v4/mqdefault.jpg",
        "is_short": None, "short_source": None, "edited": False,
    }


def test_sync_pages_through_all_uploads_and_records_quota(settings):
    gateway = FakeGateway(page_size=2)
    gateway.videos = [fake_video(f"v{i}") for i in range(5)]
    with make_client(settings, FakeGatewayProvider(gateway)) as c:
        connect(c)
        before = c.get("/api/quota").json()["used"]
        sync(c)
        quota = c.get("/api/quota").json()

    # 3 playlistItems pages + 1 videos.list batch, 1 unit each
    assert gateway.calls[-4:] == ["playlistItems.list"] * 3 + ["videos.list"]
    assert quota["used"] - before == 4
    assert quota["limit"] == 10_000
    assert quota["remaining"] == 10_000 - quota["used"]


def test_videos_are_fetched_in_batches_of_50(client, gateway):
    gateway.videos = [fake_video(f"v{i:03}") for i in range(120)]
    connect(client)
    sync(client)
    assert gateway.calls.count("videos.list") == 3
    assert len(client.get("/api/videos").json()) == 120


def test_resync_updates_changed_videos_and_drops_ones_no_longer_public(client, gateway):
    gateway.videos = [fake_video("a", title="Before"), fake_video("b")]
    connect(client)
    sync(client)

    gateway.videos = [fake_video("a", title="After"), fake_video("b", privacy_status="private")]
    sync(client)

    videos = client.get("/api/videos").json()
    assert [(v["id"], v["title"]) for v in videos] == [("a", "After")]


def test_scheduled_videos_are_excluded(client, gateway):
    # YouTube reports a scheduled upload as private until its publish time.
    gateway.videos = [fake_video("live"), fake_video("scheduled", privacy_status="private")]
    connect(client)
    sync(client)
    assert [v["id"] for v in client.get("/api/videos").json()] == ["live"]


def test_missing_uploads_playlist_never_empties_a_filled_cache(client, gateway):
    gateway.videos = [fake_video("a")]
    connect(client)
    sync(client)

    gateway.fail_with = PlaylistNotFound("uploads playlist not found")
    r = sync(client)
    assert r.status_code == 502
    gateway.fail_with = None
    assert len(client.get("/api/videos").json()) == 1


def test_channel_without_uploads_syncs_to_an_empty_cache(client, gateway):
    connect(client)
    gateway.fail_with = PlaylistNotFound("uploads playlist not found")
    r = sync(client)
    assert r.status_code == 200
    assert r.json()["video_count"] == 0


def test_sync_status_reports_last_sync_and_count(client, gateway):
    gateway.videos = [fake_video("a")]
    connect(client)
    assert client.get("/api/sync/status").json() == {"last_sync_at": None, "video_count": 0}
    sync(client)
    status = client.get("/api/sync/status").json()
    assert status["video_count"] == 1
    assert status["last_sync_at"] is not None


def test_expired_sign_in_during_sync_asks_to_reconnect(client, gateway):
    connect(client)
    gateway.fail_with = AuthExpired("Google sign-in expired")
    r = sync(client)
    assert r.status_code == 401
    assert client.get("/api/auth/status").json()["state"] == "expired"


def test_expired_sign_in_before_sync_asks_to_reconnect(settings, provider):
    with make_client(settings, provider) as c:
        connect(c)
    provider.expire()
    with make_client(settings, provider) as c:
        assert sync(c).status_code == 401


def test_results_of_a_sync_overtaken_by_a_channel_switch_are_discarded(settings, provider, gateway):
    gateway.videos = [fake_video("old_channel_video")]
    other = Channel(id="UC_other", title="Other", avatar_url=None, uploads_playlist_id="UU_other")

    with make_client(settings, provider) as c:
        connect(c)
        real_get_videos = gateway.get_videos

        def switch_channel_mid_sync(ids):
            result = real_get_videos(ids)
            gateway.channel = other
            connect(c)  # the owner reconnects as another Channel while the Sync is running
            return result

        gateway.get_videos = switch_channel_mid_sync
        r = sync(c)
        gateway.get_videos = real_get_videos

        assert r.status_code == 502
        assert "different channel" in r.json()["detail"]
        assert c.get("/api/videos").json() == []


def test_connecting_a_different_channel_clears_the_cached_videos(settings, provider, gateway):
    gateway.videos = [fake_video("a")]
    with make_client(settings, provider) as c:
        connect(c)
        sync(c)
        gateway.channel = Channel(id="UC_other", title="Other", avatar_url=None, uploads_playlist_id="UU_other")
        connect(c)
        assert c.get("/api/videos").json() == []
