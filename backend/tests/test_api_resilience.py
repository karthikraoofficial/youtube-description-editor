"""Retries, quota stops and Resume, through the HTTP seam (sleeps are injected, so tests don't wait)."""
from app.youtube.errors import QuotaExceeded, RetryableError
from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS, FakeClock, drive, make_client, sign_in


def review_and_apply(client, gateway, videos):
    gateway.videos = videos
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)
    cs = client.post("/api/changesets", json={"operation": {"type": "append", "text": "Footer"},
                                              "video_ids": [v.id for v in videos]}, headers=CLIENT_HEADERS).json()
    run_id = client.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": cs["counts"]["to_write"]},
                         headers=CLIENT_HEADERS).json()["id"]
    drive(client, run_id)
    return run_id


def run_of(client, run_id):
    r = client.get(f"/api/runs/{run_id}").json()
    return r["status"], {i["video_id"]: i["status"] for i in r["items"]}, r


def resume(client, run_id, count):
    r = client.post(f"/api/runs/{run_id}/resume", json={"confirm_count": count}, headers=CLIENT_HEADERS)
    if r.status_code == 202:
        drive(client, run_id)
    return r


def test_transient_errors_are_retried_with_growing_backoff(client, gateway, sleeps):
    gateway.fail_updates["a"] = [RetryableError("YouTube API error 503: backendError"),
                                 RetryableError("YouTube API error 429: rateLimitExceeded")]
    status, items, run = run_of(client, review_and_apply(client, gateway, [fake_video("a", description="Song")]))
    assert (status, items) == ("completed", {"a": "success"})
    assert gateway.calls.count("videos.update") == 3
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0]  # exponential, with jitter
    assert any("retrying" in entry["message"] for entry in run["log"])


def test_when_retries_run_out_the_video_fails_and_the_run_goes_on(client, gateway, sleeps):
    gateway.fail_updates["a"] = [RetryableError("YouTube API error 500: backendError")] * 10
    status, items, run = run_of(client, review_and_apply(
        client, gateway, [fake_video("a", description="Song"), fake_video("b", description="Two")]))
    assert (status, items) == ("completed", {"a": "failed", "b": "success"})
    failed = next(i for i in run["items"] if i["video_id"] == "a")
    assert failed["attempts"] == 5
    assert "500" in failed["error"]


def test_the_fresh_fetch_is_retried_too(client, gateway, sleeps):
    gateway.fail_snippet_calls = [RetryableError("YouTube API error 503: backendError")]
    status, items, _ = run_of(client, review_and_apply(client, gateway, [fake_video("a", description="Song")]))
    assert (status, items) == ("completed", {"a": "success"})


def test_resume_after_the_quota_ran_out_finishes_without_writing_twice(client, gateway, sleeps):
    gateway.fail_updates["b"] = [QuotaExceeded("quotaExceeded")]
    run_id = review_and_apply(client, gateway, [fake_video(v, description="Song") for v in ("a", "b", "c")])
    assert run_of(client, run_id)[0] == "paused_quota"

    r = resume(client, run_id, 2)
    assert r.status_code == 202
    status, items, _ = run_of(client, run_id)
    assert (status, items) == ("completed", {"a": "success", "b": "success", "c": "success"})
    assert [vid for vid, _ in gateway.updates] == ["a", "b", "c"]  # a was not written again


def test_resume_needs_the_number_of_videos_left(client, gateway, sleeps):
    gateway.fail_updates["b"] = [QuotaExceeded("quotaExceeded")]
    run_id = review_and_apply(client, gateway, [fake_video(v, description="Song") for v in ("a", "b")])
    r = resume(client, run_id, 2)
    assert r.status_code == 409
    assert "1" in r.json()["detail"]
    assert run_of(client, run_id)[0] == "paused_quota"


def test_finished_runs_cannot_be_resumed(client, gateway, sleeps):
    run_id = review_and_apply(client, gateway, [fake_video("a", description="Song")])
    assert resume(client, run_id, 0).status_code == 409


def test_an_interrupted_run_resumes_and_a_video_written_just_before_the_crash_counts_as_done(
        settings, provider, gateway, sleeps):
    from app.runs import LEASE_S

    clock = FakeClock()
    with make_client(settings, provider, clock=clock) as c:
        gateway.fail_updates["b"] = [QuotaExceeded("quotaExceeded")]
        run_id = review_and_apply(c, gateway, [fake_video(v, description="Song") for v in ("a", "b", "c")])
        app = c.app
        # Simulate a crash after YouTube took b's write but before it was recorded, and the app closing.
        gateway.set_description("b", "Song\n\nFooter")
        with app.state.store.tx() as conn:
            conn.execute("UPDATE runs SET status = 'running' WHERE id = ?", (run_id,))
    clock.advance(LEASE_S + 1)  # nobody drives it any more
    with make_client(settings, provider, clock=clock) as c:
        assert run_of(c, run_id)[0] == "interrupted"  # nothing resumes on its own (ADR-0007)
        assert resume(c, run_id, 2).status_code == 202
        status, items, run = run_of(c, run_id)
    assert (status, items) == ("completed", {"a": "success", "b": "success", "c": "success"})
    assert [vid for vid, _ in gateway.updates] == ["a", "c"]  # b was already written, so not sent again
    assert any("already" in entry["message"] for entry in run["log"])


def test_runs_that_can_be_resumed_are_listed_for_the_owner(client, gateway, sleeps):
    gateway.fail_updates["b"] = [QuotaExceeded("quotaExceeded")]
    run_id = review_and_apply(client, gateway, [fake_video(v, description="Song") for v in ("a", "b")])
    unfinished = client.get("/api/runs?unfinished=true").json()
    assert [(r["id"], r["status"], r["counts"]["pending"]) for r in unfinished] == [(run_id, "paused_quota", 1)]


def test_text_already_matching_on_a_first_run_is_a_no_op_not_a_write_we_made(client, gateway, sleeps):
    gateway.videos = [fake_video("a", description="Song")]
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)
    cs = client.post("/api/changesets", json={"operation": {"type": "append", "text": "Footer"}, "video_ids": ["a"]},
                     headers=CLIENT_HEADERS).json()
    gateway.set_description("a", "Song\n\nFooter")  # the owner typed exactly this in Studio
    run_id = client.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": 1},
                         headers=CLIENT_HEADERS).json()["id"]
    drive(client, run_id)
    status, items, _ = run_of(client, run_id)
    assert (status, items) == ("completed", {"a": "noop"})
    assert gateway.updates == []
    assert client.get("/api/videos").json()[0]["edited"] is False


def test_attempts_count_every_try_even_when_the_last_error_is_permanent(client, gateway, sleeps):
    from app.youtube.errors import GatewayError

    gateway.fail_updates["a"] = [RetryableError("503"), RetryableError("503"), GatewayError("400 invalidDescription")]
    _, items, run = run_of(client, review_and_apply(client, gateway, [fake_video("a", description="Song")]))
    assert items == {"a": "failed"}
    assert run["items"][0]["attempts"] == 3
