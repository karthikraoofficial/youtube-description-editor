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


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, fake=True)


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
