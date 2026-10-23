"""The Store runs on SQLite (local mode) or Postgres (DATABASE_URL), with the same behaviour (ADR-0016)."""
import pytest

from tests.conftest import CLIENT_HEADERS, TEST_DATABASE_URL, make_client, sign_in
from app.youtube.fake import sample_videos


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="set YDE_TEST_DATABASE_URL to run on Postgres")
def test_with_a_database_url_nothing_is_written_to_the_data_dir(settings, provider, gateway):
    gateway.videos = sample_videos()
    with make_client(settings, provider) as client:
        sign_in(client)
        assert client.post("/api/sync", headers=CLIENT_HEADERS).status_code == 200

    assert not settings.db_path.exists()
    with make_client(settings, provider) as again:  # a fresh app, as on another serverless instance
        assert len(again.get("/api/videos").json()) > 0


def test_the_cache_survives_a_fresh_app(settings, provider, gateway):
    gateway.videos = sample_videos()
    with make_client(settings, provider) as client:
        sign_in(client)
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
        sign_in(client)
        count = client.post("/api/sync", headers=CLIENT_HEADERS).json()["video_count"]

    assert open_store(settings).video_count() == count  # migrates again: no error, nothing lost


def test_a_store_installed_without_its_migrations_refuses_to_start(tmp_path, monkeypatch):
    import app.store.engines as engines

    monkeypatch.setattr(engines, "MIGRATIONS_ROOT", tmp_path / "missing")
    with pytest.raises(RuntimeError, match="migrations"):
        engines.SqliteEngine(tmp_path / "app.db").migrate()


def test_the_backend_package_ships_its_migrations():
    import tomllib
    from pathlib import Path

    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert "migrations/*/*.sql" in pyproject["tool"]["setuptools"]["package-data"]["app.store"]
