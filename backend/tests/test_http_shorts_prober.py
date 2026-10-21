"""How the real prober reads YouTube's answers, with the network replaced by httpx.MockTransport."""
import httpx
import pytest

from app import shorts
from app.shorts import HttpShortsProber


def prober_answering(handler):
    return HttpShortsProber(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def no_spacing(monkeypatch):
    monkeypatch.setattr(shorts, "PROBE_SPACING_S", 0)


def test_200_means_short():
    assert prober_answering(lambda req: httpx.Response(200)).probe("abc") is True


def test_redirect_to_watch_means_not_short():
    p = prober_answering(lambda req: httpx.Response(303, headers={"location": "https://www.youtube.com/watch?v=abc"}))
    assert p.probe("abc") is False


@pytest.mark.parametrize("response", [
    httpx.Response(302, headers={"location": "https://consent.youtube.com/m?continue=..."}),  # EU consent wall
    httpx.Response(429),
    httpx.Response(500),
])
def test_anything_else_means_unknown(response):
    assert prober_answering(lambda req: response).probe("abc") is None


def test_network_errors_mean_unknown():
    def fail(req):
        raise httpx.ConnectError("offline")

    assert prober_answering(fail).probe("abc") is None


def test_it_asks_the_shorts_url_without_following_redirects():
    seen = []

    def record(req):
        seen.append((req.method, str(req.url)))
        return httpx.Response(303, headers={"location": "https://www.youtube.com/watch?v=abc"})

    prober_answering(record).probe("abc")
    assert seen == [("HEAD", "https://www.youtube.com/shorts/abc")]
