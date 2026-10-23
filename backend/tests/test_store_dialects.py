"""The Store runs on SQLite (local mode) or Postgres (DATABASE_URL), with the same behaviour (ADR-0016)."""
import pytest

from tests.conftest import CLIENT_HEADERS, TEST_DATABASE_URL, make_client
from app.youtube.fake import sample_videos


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="set YDE_TEST_DATABASE_URL to run on Postgres")
def test_with_a_database_url_nothing_is_written_to_the_data_dir(settings, provider, gateway):
    gateway.videos = sample_videos()
    with make_client(settings, provider) as client:
        client.post("/api/auth/connect", headers=CLIENT_HEADERS)
        assert client.post("/api/sync", headers=CLIENT_HEADERS).status_code == 200

    assert not settings.db_path.exists()
    with make_client(settings, provider) as again:  # a fresh app, as on another serverless instance
        assert len(again.get("/api/videos").json()) > 0


def test_the_cache_survives_a_fresh_app(settings, provider, gateway):
    gateway.videos = sample_videos()
    with make_client(settings, provider) as client:
        client.post("/api/auth/connect", headers=CLIENT_HEADERS)
        synced = client.post("/api/sync", headers=CLIENT_HEADERS).json()

    with make_client(settings, provider) as again:
        assert len(again.get("/api/videos").json()) == synced["video_count"]


def test_placeholders_in_comments_and_quotes_are_left_alone():
    from app.store.engines import to_pyformat

    sql = "SELECT '?', \"a?\" -- don't ? here\nFROM t WHERE a = ? AND b LIKE '%x'"
    assert to_pyformat(sql) == "SELECT '?', \"a?\" -- don't ? here\nFROM t WHERE a = %s AND b LIKE '%%x'"


def test_migrating_an_up_to_date_database_changes_nothing(settings, provider, gateway):
    from app.store.db import open_store

    gateway.videos = sample_videos()
    with make_client(settings, provider) as client:
        client.post("/api/auth/connect", headers=CLIENT_HEADERS)
        count = client.post("/api/sync", headers=CLIENT_HEADERS).json()["video_count"]

    assert open_store(settings).video_count() == count  # migrates again: no error, nothing lost
