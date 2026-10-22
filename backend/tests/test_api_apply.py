"""The apply Run, end to end through the HTTP seam with the fake YouTube (no real writes)."""
import json

from app.youtube.errors import GatewayError
from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS

APPEND = {"type": "append", "text": "Footer"}


def review(client, gateway, videos, op=APPEND):
    gateway.videos = videos
    client.post("/api/auth/connect", headers=CLIENT_HEADERS)
    client.post("/api/sync", headers=CLIENT_HEADERS)
    r = client.post("/api/changesets", json={"operation": op, "video_ids": [v.id for v in videos]},
                    headers=CLIENT_HEADERS)
    return r.json()


def apply(client, cs, confirm_count=None):
    count = cs["counts"]["to_write"] if confirm_count is None else confirm_count
    return client.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": count}, headers=CLIENT_HEADERS)


def statuses(client, run_id):
    run = client.get(f"/api/runs/{run_id}").json()
    return run["status"], {i["video_id"]: i["status"] for i in run["items"]}


TAGGED = dict(tags=("guitar", "metal"), category_id="10", default_language="en", default_audio_language="en-IN")


def test_a_wrong_confirm_count_is_refused_and_nothing_is_written(client, gateway):
    cs = review(client, gateway, [fake_video("a", description="Song")])
    r = apply(client, cs, confirm_count=5)
    assert r.status_code == 409
    assert "videos.update" not in gateway.calls
    assert gateway.updates == []


def test_happy_path_writes_only_the_description_and_round_trips_the_snippet(client, gateway):
    cs = review(client, gateway, [fake_video("a", title="Riff", description="Song", **TAGGED),
                                  fake_video("b", title="Jam", description="Jam session")])
    r = apply(client, cs)
    assert r.status_code == 202
    status, items = statuses(client, r.json()["id"])
    assert (status, items) == ("completed", {"a": "success", "b": "success"})

    bodies = dict(gateway.updates)
    assert bodies["a"] == {"title": "Riff", "description": "Song\n\nFooter", "categoryId": "10",
                           "tags": ["guitar", "metal"], "defaultLanguage": "en", "defaultAudioLanguage": "en-IN"}
    # Optional fields the Video doesn't have are left out, never sent as empty values.
    assert bodies["b"] == {"title": "Jam", "description": "Jam session\n\nFooter", "categoryId": "10"}


def test_backups_are_saved_before_the_first_write(client, gateway, settings):
    cs = review(client, gateway, [fake_video("a", description="Song"), fake_video("b", description="Two")])
    gateway.calls.clear()
    gateway.check_backups_in = settings.backups_dir
    run_id = apply(client, cs).json()["id"]

    first_write = gateway.calls.index("videos.update")
    assert gateway.backup_seen_at_first_write is True  # the fake checks the backup file when the first write lands
    assert "videos.list" in gateway.calls[:first_write]
    backup = json.loads((settings.backups_dir / f"run-{run_id}.json").read_text(encoding="utf-8"))
    assert {b["video_id"]: b["snippet"]["description"] for b in backup["videos"]} == {"a": "Song", "b": "Two"}
    run = client.get(f"/api/runs/{run_id}").json()
    assert all(i["has_backup"] for i in run["items"])


def test_a_video_edited_in_studio_since_the_review_is_skipped_as_stale(client, gateway):
    cs = review(client, gateway, [fake_video("a", description="Song"), fake_video("b", description="Two")])
    gateway.set_description("a", "Changed in YouTube Studio")
    _, items = statuses(client, apply(client, cs).json()["id"])
    assert items == {"a": "stale", "b": "success"}
    assert [vid for vid, _ in gateway.updates] == ["b"]
    assert gateway.description_of("a") == "Changed in YouTube Studio"


def test_a_failed_video_never_stops_the_run(client, gateway):
    cs = review(client, gateway, [fake_video(v, description="Song") for v in ("a", "b", "c")])
    gateway.fail_updates["b"] = GatewayError("YouTube API error 400: invalidDescription")
    run_id = apply(client, cs).json()["id"]
    status, items = statuses(client, run_id)
    assert (status, items) == ("completed", {"a": "success", "b": "failed", "c": "success"})
    failed = next(i for i in client.get(f"/api/runs/{run_id}").json()["items"] if i["video_id"] == "b")
    assert "invalidDescription" in failed["error"]


def test_a_video_that_disappeared_fails_without_a_write(client, gateway):
    cs = review(client, gateway, [fake_video("a", description="Song"), fake_video("gone", description="x")])
    gateway.videos = [v for v in gateway.videos if v.id != "gone"]
    _, items = statuses(client, apply(client, cs).json()["id"])
    assert items == {"a": "success", "gone": "failed"}


def test_only_videos_to_write_are_part_of_the_run_and_no_ops_cost_nothing(client, gateway):
    cs = review(client, gateway, [
        fake_video("write", description="Song"),
        fake_video("excl", description="Other"),
        fake_video("same", description="Song\n\nFooter"),  # skip_if_present: unchanged
        fake_video("big", description="x" * 4999),          # blocked
    ])
    client.patch(f"/api/changesets/{cs['id']}/items/excl", json={"included": False}, headers=CLIENT_HEADERS)
    cs = client.get(f"/api/changesets/{cs['id']}").json()
    before = client.get("/api/quota").json()["used"]

    run = client.get(f"/api/runs/{apply(client, cs).json()['id']}").json()

    assert [i["video_id"] for i in run["items"]] == ["write"]
    assert [vid for vid, _ in gateway.updates] == ["write"]
    # One videos.list batch (1 unit) for the fresh fetch + one update (50 units).
    assert client.get("/api/quota").json()["used"] - before == 51


def test_written_videos_show_as_edited_with_their_new_description(client, gateway):
    cs = review(client, gateway, [fake_video("a", description="Song"), fake_video("b", description="Two")])
    apply(client, cs)
    videos = {v["id"]: v for v in client.get("/api/videos").json()}
    assert (videos["a"]["edited"], videos["a"]["description"]) == (True, "Song\n\nFooter")


def test_a_review_can_only_be_applied_once(client, gateway):
    cs = review(client, gateway, [fake_video("a", description="Song")])
    assert apply(client, cs).status_code == 202
    again = apply(client, cs)
    assert again.status_code == 409
    assert len(gateway.updates) == 1
    assert client.get(f"/api/changesets/{cs['id']}").json()["status"] == "applied"


def test_hand_edits_are_what_gets_written(client, gateway):
    cs = review(client, gateway, [fake_video("a", description="Song")])
    client.patch(f"/api/changesets/{cs['id']}/items/a", json={"override": "My own text"}, headers=CLIENT_HEADERS)
    apply(client, cs)
    assert dict(gateway.updates)["a"]["description"] == "My own text"


def test_the_target_is_revalidated_before_writing(client, gateway, app):
    """Defence in depth: even if a bad target reached a Run, the engine refuses to send it."""
    cs = review(client, gateway, [fake_video("a", description="Song")])
    with app.state.store.tx() as conn:  # simulate a corrupted review row
        conn.execute("UPDATE changeset_items SET computed_description = 'bad <tag>' WHERE video_id = 'a'")
    _, items = statuses(client, apply(client, cs).json()["id"])
    assert items == {"a": "blocked"}
    assert gateway.updates == []


def test_running_out_of_quota_stops_the_run_and_keeps_the_rest_queued(client, gateway):
    from app.youtube.errors import QuotaExceeded

    cs = review(client, gateway, [fake_video(v, description="Song") for v in ("a", "b", "c")])
    gateway.fail_updates["b"] = QuotaExceeded("YouTube API error 403: quotaExceeded")
    status, items = statuses(client, apply(client, cs).json()["id"])
    assert (status, items) == ("paused_quota", {"a": "success", "b": "pending", "c": "pending"})
    assert gateway.calls.count("videos.update") == 2  # c was never attempted
    assert client.get("/api/quota").json()["remaining"] == 0  # today is marked as used up


def test_a_run_left_running_by_a_crash_is_interrupted_at_startup(settings, provider, gateway):
    from .conftest import make_client

    with make_client(settings, provider) as c:
        cs = review(c, gateway, [fake_video("a", description="Song")])
        app = c.app
        # Simulate the app closing mid-run: the Run is still marked running.
        with app.state.store.tx() as conn:
            conn.execute("INSERT INTO runs (kind, changeset_id, status, created_at) "
                         "VALUES ('apply', ?, 'running', '2026-01-01T00:00:00+00:00')", (cs["id"],))
    with make_client(settings, provider) as c:
        runs = c.get("/api/runs").json()
    assert [r["status"] for r in runs] == ["interrupted"]


def test_two_apply_requests_for_one_review_make_one_run(client, gateway, app):
    cs = review(client, gateway, [fake_video("a", description="Song")])
    runs = app.state.runs
    first = runs.apply_changeset(cs["id"], 1)
    import pytest

    from app.runs import RunConflict
    with pytest.raises(RunConflict):
        runs.apply_changeset(cs["id"], 1)
    assert [r["id"] for r in runs.list()] == [first]
