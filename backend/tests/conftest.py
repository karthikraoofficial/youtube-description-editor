import pytest
from fastapi.testclient import TestClient

from app.config import CLIENT_HEADER, CLIENT_HEADER_VALUE, Settings
from app.main import create_app
from app.shorts import FakeShortsProber
from app.youtube.fake import FakeGateway, FakeGatewayProvider

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
    return create_app(settings, provider=provider, prober=prober)


@pytest.fixture
def client(app):
    with TestClient(app, base_url=BASE_URL) as c:
        yield c


def make_client(settings, provider, prober=None):
    """A fresh app on the same data dir, as after restarting the app."""
    app = create_app(settings, provider=provider, prober=prober or FakeShortsProber(default=False))
    return TestClient(app, base_url=BASE_URL)
