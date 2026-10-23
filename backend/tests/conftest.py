import os
from concurrent.futures import Executor, Future

import pytest
from fastapi.testclient import TestClient

from app.config import CLIENT_HEADER, CLIENT_HEADER_VALUE, Settings
from app.main import create_app
from app.shorts import FakeShortsProber
from app.youtube.fake import FakeGateway, FakeGatewayProvider



class ImmediateExecutor(Executor):
    """Runs a Run synchronously, so it has finished when the request returns."""

    def submit(self, fn, /, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as e:  # surface it like a real executor would
            future.set_exception(e)
        return future


CLIENT_HEADERS = {CLIENT_HEADER: CLIENT_HEADER_VALUE}
BASE_URL = "http://127.0.0.1"


# Set to a Postgres URL to run the whole suite on Postgres instead of SQLite (ADR-0016).
TEST_DATABASE_URL = os.environ.get("YDE_TEST_DATABASE_URL") or None


@pytest.fixture
def settings(tmp_path):
    if TEST_DATABASE_URL:
        _empty_postgres(TEST_DATABASE_URL)
    return Settings(data_dir=tmp_path, fake=True, database_url=TEST_DATABASE_URL)


def _empty_postgres(url: str) -> None:
    """Every test starts from an empty database; the schema itself is kept."""
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() AND tablename != 'schema_migrations'")]
        if tables:
            conn.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")


@pytest.fixture
def gateway():
    return FakeGateway()


@pytest.fixture
def provider(gateway):
    return FakeGatewayProvider(gateway)


@pytest.fixture
def prober():
    return FakeShortsProber(default=False)


@pytest.fixture
def app(settings, provider, prober):
    return create_app(settings, provider=provider, prober=prober, run_executor=ImmediateExecutor())


@pytest.fixture
def client(app):
    with TestClient(app, base_url=BASE_URL) as c:
        yield c


def make_client(settings, provider, prober=None):
    """A fresh app on the same data dir, as after restarting the app."""
    app = create_app(settings, provider=provider, prober=prober or FakeShortsProber(default=False),
                     run_executor=ImmediateExecutor())
    return TestClient(app, base_url=BASE_URL)


@pytest.fixture
def sleeps(monkeypatch):
    """Record the Run engine's backoff sleeps instead of waiting."""
    import app.runs as runs

    recorded: list[float] = []
    monkeypatch.setattr(runs, "sleep", recorded.append)
    return recorded
