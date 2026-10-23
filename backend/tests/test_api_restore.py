"""History and Restore through the HTTP seam (ADR-0004: a Restore is a new, description-only Run)."""
from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS, drive


def apply_append(client, gateway, videos, text="Footer"):
    if videos is not None:
        gateway.videos = videos
        client.post("/api/auth/connect", headers=CLIENT_HEADERS)
        client.post("/api/sync", headers=CLIENT_HEADERS)
    ids = [v.id for v in gateway.videos]
    cs = client.post("/api/changesets", json={"operation": {"type": "append", "text": text}, "video_ids": ids},
                     headers=CLIENT_HEADERS).json()
    run_id = client.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": cs["counts"]["to_write"]},
                         headers=CLIENT_HEADERS).json()["id"]
    drive(client, run_id)
    return run_id


def restore(client, run_id, count, video_ids=None):
    body = {"confirm_count": count} | ({"video_ids": video_ids} if video_ids is not None else {})
    r = client.post(f"/api/runs/{run_id}/restore", json=body, headers=CLIENT_HEADERS)
    if r.status_code == 202:
        drive(client, r.json()["id"])
    return r


def statuses(client, run_id):
    r = client.get(f"/api/runs/{run_id}").json()
    return r["status"], {i["video_id"]: i["status"] for i in r["items"]}


def test_restoring_a_run_puts_the_backed_up_descriptions_back(client, gateway, sleeps):
    run_id = apply_append(client, gateway, [fake_video("a", description="One"), fake_video("b", description="Two")])
    r = restore(client, run_id, 2)
    assert r.status_code == 202
    restore_id = r.json()["id"]
    assert statuses(client, restore_id) == ("completed", {"a": "success", "b": "success"})
    assert (gateway.description_of("a"), gateway.description_of("b")) == ("One", "Two")
    run = client.get(f"/api/runs/{restore_id}").json()
    assert (run["kind"], run["source_run_id"]) == ("restore", run_id)


def test_restore_keeps_todays_title_and_tags(client, gateway, sleeps):
    from dataclasses import replace

    run_id = apply_append(client, gateway, [fake_video("a", title="Old title", description="One", tags=("x",))])
    gateway.videos = [replace(v, title="Renamed in Studio", tags=("y", "z")) for v in gateway.videos]
    restore(client, run_id, 1)
    body = gateway.updates[-1][1]
    assert (body["title"], body["tags"], body["description"]) == ("Renamed in Studio", ["y", "z"], "One")


def test_restoring_one_video(client, gateway, sleeps):
    run_id = apply_append(client, gateway, [fake_video("a", description="One"), fake_video("b", description="Two")])
    restore_id = restore(client, run_id, 1, ["b"]).json()["id"]
    assert statuses(client, restore_id) == ("completed", {"b": "success"})
    assert (gateway.description_of("a"), gateway.description_of("b")) == ("One\n\nFooter", "Two")


def test_a_video_changed_since_the_run_is_not_overwritten(client, gateway, sleeps):
    run_id = apply_append(client, gateway, [fake_video("a", description="One")])
    gateway.set_description("a", "Edited again in Studio")
    restore_id = restore(client, run_id, 1).json()["id"]
    assert statuses(client, restore_id) == ("completed", {"a": "stale"})
    assert gateway.description_of("a") == "Edited again in Studio"


def test_restore_needs_the_matching_count_and_writes_nothing_otherwise(client, gateway, sleeps):
    run_id = apply_append(client, gateway, [fake_video("a", description="One")])
    writes = len(gateway.updates)
    assert restore(client, run_id, 5).status_code == 409
    assert len(gateway.updates) == writes


def test_only_videos_the_run_actually_wrote_can_be_restored(client, gateway, sleeps):
    from app.youtube.errors import GatewayError

    gateway.fail_updates["b"] = GatewayError("400 invalid")
    run_id = apply_append(client, gateway, [fake_video("a", description="One"), fake_video("b", description="Two")])
    assert restore(client, run_id, 1, ["b"]).status_code == 422
    assert restore(client, run_id, 1).json()["id"]  # whole-run restore covers just the written one


def test_a_restore_can_itself_be_restored(client, gateway, sleeps):
    run_id = apply_append(client, gateway, [fake_video("a", description="One")])
    restore_id = restore(client, run_id, 1).json()["id"]
    again = restore(client, restore_id, 1).json()["id"]
    assert statuses(client, again) == ("completed", {"a": "success"})
    assert gateway.description_of("a") == "One\n\nFooter"


def test_history_lists_runs_newest_first_with_what_they_did(client, gateway, sleeps):
    run_id = apply_append(client, gateway, [fake_video("a", description="One")])
    restore_id = restore(client, run_id, 1).json()["id"]
    runs = client.get("/api/runs").json()
    assert [(r["id"], r["kind"], r["source_run_id"], r["counts"]["success"]) for r in runs] == [
        (restore_id, "restore", run_id, 1), (run_id, "apply", None, 1)]
    assert runs[1]["operation"]["type"] == "append"
    assert runs[1]["restorable"] == 1


def test_a_run_that_is_still_writing_cannot_be_restored_yet(client, gateway, app, sleeps):
    run_id = apply_append(client, gateway, [fake_video("a", description="One")])
    with app.state.store.tx() as conn:
        conn.execute("UPDATE runs SET status = 'running' WHERE id = ?", (run_id,))
    r = restore(client, run_id, 1)
    assert r.status_code == 409
    assert "still" in r.json()["detail"]


def test_an_empty_video_list_is_a_clear_error(client, gateway, sleeps):
    run_id = apply_append(client, gateway, [fake_video("a", description="One")])
    r = restore(client, run_id, 0, [])
    assert r.status_code == 422


def test_a_skipped_restore_says_what_changed(client, gateway, sleeps):
    run_id = apply_append(client, gateway, [fake_video("a", description="One")])
    gateway.set_description("a", "Edited again")
    restore_id = restore(client, run_id, 1).json()["id"]
    item = client.get(f"/api/runs/{restore_id}").json()["items"][0]
    assert item["error"] == f"Changed on YouTube since run #{run_id} wrote it; left as it is."


def test_each_item_says_whether_it_can_be_restored(client, gateway, sleeps):
    from app.youtube.errors import GatewayError

    gateway.fail_updates["b"] = GatewayError("400 invalid")
    run_id = apply_append(client, gateway, [fake_video("a", description="One"), fake_video("b", description="Two")])
    items = {i["video_id"]: i["restorable"] for i in client.get(f"/api/runs/{run_id}").json()["items"]}
    assert items == {"a": True, "b": False}


def test_a_second_restore_while_one_is_under_way_is_refused(client, gateway, app, sleeps):
    run_id = apply_append(client, gateway, [fake_video("a", description="One")])
    with app.state.store.tx() as conn:  # a restore of this run that another tab is still driving
        conn.execute("INSERT INTO runs (kind, source_run_id, status, created_at, driver, lease_until) "
                     "VALUES ('restore', ?, 'running', '2026-01-01T00:00:00+00:00', 'other-tab', ?)",
                     (run_id, 4_000_000_000))
    r = restore(client, run_id, 1)
    assert r.status_code == 409
    assert "already restoring" in r.json()["detail"]


def test_history_carries_a_readable_operation_summary(client, gateway, sleeps):
    apply_append(client, gateway, [fake_video("a", description="One")], text="Guitar lessons")
    assert client.get("/api/runs").json()[0]["operation_summary"] == 'Append to Description: "Guitar lessons"'
