from app.shorts import FakeShortsProber
from app.youtube.fake import FakeGateway, FakeGatewayProvider, fake_video

from .conftest import CLIENT_HEADERS, make_client, sign_in


def run(settings, gateway, prober, *, syncs=1):
    with make_client(settings, FakeGatewayProvider(gateway), prober=prober) as c:
        sign_in(c)
        for _ in range(syncs):
            assert c.post("/api/sync", headers=CLIENT_HEADERS).status_code == 200
        return {v["id"]: (v["is_short"], v["short_source"]) for v in c.get("/api/videos").json()}


def test_sync_classifies_videos_by_probing(settings):
    gateway = FakeGateway()
    gateway.videos = [fake_video("short", duration_s=150), fake_video("long_but_short_ish", duration_s=144)]
    prober = FakeShortsProber({"short": True, "long_but_short_ish": False})

    assert run(settings, gateway, prober) == {
        "short": (True, "probe"),
        "long_but_short_ish": (False, "probe"),  # duration alone would have called this a Short
    }


def test_failed_probe_falls_back_to_duration(settings):
    gateway = FakeGateway()
    gateway.videos = [fake_video("a", duration_s=180), fake_video("b", duration_s=181), fake_video("c", duration_s=0)]
    prober = FakeShortsProber({})  # every probe fails

    assert run(settings, gateway, prober) == {
        "a": (True, "duration"),
        "b": (False, "duration"),
        "c": (None, None),  # unknown duration: stays unclassified rather than guessed
    }


def test_probed_videos_are_not_probed_again_but_fallbacks_are_retried(settings):
    gateway = FakeGateway()
    gateway.videos = [fake_video("probed"), fake_video("fallback", duration_s=60)]
    prober = FakeShortsProber({"probed": False})

    result = run(settings, gateway, prober, syncs=2)

    assert prober.calls.count("probed") == 1
    assert prober.calls.count("fallback") == 2
    assert result["fallback"] == (True, "duration")


def test_manual_override_wins_and_survives_resync(settings):
    gateway = FakeGateway()
    gateway.videos = [fake_video("v", duration_s=40)]
    prober = FakeShortsProber({"v": True})
    with make_client(settings, FakeGatewayProvider(gateway), prober=prober) as c:
        sign_in(c)
        c.post("/api/sync", headers=CLIENT_HEADERS)

        r = c.patch("/api/videos/v", json={"is_short": False}, headers=CLIENT_HEADERS)
        assert r.status_code == 200
        assert (r.json()["is_short"], r.json()["short_source"]) == (False, "manual")

        c.post("/api/sync", headers=CLIENT_HEADERS)
        v = c.get("/api/videos").json()[0]

    assert (v["is_short"], v["short_source"]) == (False, "manual")
    assert prober.calls == ["v"]


class ExplodingProber(FakeShortsProber):
    def probe(self, video_id):
        super().probe(video_id)
        raise RuntimeError("unexpected")


def test_a_crashing_probe_never_fails_the_sync(settings):
    gateway = FakeGateway()
    gateway.videos = [fake_video("a", duration_s=30), fake_video("b", duration_s=900)]
    assert run(settings, gateway, ExplodingProber()) == {"a": (True, "duration"), "b": (False, "duration")}


def test_probing_stops_at_the_time_budget_and_falls_back(settings, monkeypatch):
    import app.shorts as shorts

    monkeypatch.setattr(shorts, "PROBE_BUDGET_S", 0)  # budget already spent: no probes at all
    gateway = FakeGateway()
    gateway.videos = [fake_video("a", duration_s=30)]
    prober = FakeShortsProber({"a": False})
    assert run(settings, gateway, prober) == {"a": (True, "duration")}
    assert prober.calls == []


def test_overriding_an_unknown_video_is_404(client):
    r = client.patch("/api/videos/nope", json={"is_short": True}, headers=CLIENT_HEADERS)
    assert r.status_code == 404
