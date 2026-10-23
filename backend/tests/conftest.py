import os

import pytest
from fastapi.testclient import TestClient

from app.config import CLIENT_HEADER, CLIENT_HEADER_VALUE, Settings
from app.main import create_app
from app.shorts import FakeShortsProber
from app.youtube.fake import FakeGateway, FakeGatewayProvider



class FakeClock:
    """Time for leases and Step budgets, moved on by the test instead of by waiting."""

    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


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
def clock():
    return FakeClock()


@pytest.fixture
def app(settings, provider, prober, clock):
    return create_app(settings, provider=provider, prober=prober, clock=clock)


@pytest.fixture
def client(app):
    with TestClient(app, base_url=BASE_URL) as c:
        yield c


def make_client(settings, provider, prober=None, clock=None):
    """A fresh app on the same data dir, as after restarting the app."""
    app = create_app(settings, provider=provider, prober=prober or FakeShortsProber(default=False),
                     clock=clock or FakeClock())
    return TestClient(app, base_url=BASE_URL)


DRIVER = "tab-0000-test"


def step(client, run_id, driver=DRIVER):
    return client.post(f"/api/runs/{run_id}/step", json={"driver": driver}, headers=CLIENT_HEADERS)


def drive(client, run_id, driver=DRIVER):
    """What the Run screen does after Apply, Restore or Resume: Step until the Run stops."""
    for _ in range(100):
        r = step(client, run_id, driver)
        if r.status_code != 200 or r.json()["run"]["status"] not in ("pending", "running"):
            return r
    raise AssertionError(f"run {run_id} never stopped")


@pytest.fixture
def sleeps(monkeypatch):
    """Record the Run engine's backoff sleeps instead of waiting."""
    import app.runs as runs

    recorded: list[float] = []
    monkeypatch.setattr(runs, "sleep", recorded.append)
    return recorded
