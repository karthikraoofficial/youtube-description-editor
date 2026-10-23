"""The browser drives a Run in Steps, holding a lease (ADR-0017), through the HTTP seam."""
from app.runs import LEASE_S, STEP_BUDGET_S
from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS, drive, sign_in, step


def apply_without_driving(client, gateway, ids):
    gateway.videos = [fake_video(v, description="Song") for v in ids]
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)
    cs = client.post("/api/changesets", json={"operation": {"type": "append", "text": "Footer"}, "video_ids": ids},
                     headers=CLIENT_HEADERS).json()
    r = client.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": len(ids)}, headers=CLIENT_HEADERS)
    assert r.status_code == 202
    return r.json()["id"]


def run_of(client, run_id):
    r = client.get(f"/api/runs/{run_id}").json()
    return r["status"], {i["video_id"]: i["status"] for i in r["items"]}


def test_apply_writes_nothing_until_the_first_step(client, gateway):
    run_id = apply_without_driving(client, gateway, ["a", "b"])
    assert run_of(client, run_id) == ("pending", {"a": "pending", "b": "pending"})
    assert gateway.updates == []

    r = drive(client, run_id)
    assert r.status_code == 200
    assert r.json()["run"]["status"] == "completed"
    assert {i["video_id"]: i["status"] for i in r.json()["items"]} == {"a": "success", "b": "success"}
    assert r.json()["quota"]["limit"] == 10_000


def test_a_step_stops_starting_videos_once_its_time_is_used_and_the_next_step_carries_on(client, gateway, clock):
    run_id = apply_without_driving(client, gateway, ["a", "b", "c"])
    gateway.after_update = lambda: clock.advance(STEP_BUDGET_S + 1)  # writing a takes the whole budget

    first = step(client, run_id).json()
    assert first["run"]["status"] == "running"
    assert [vid for vid, _ in gateway.updates] == ["a"]

    assert drive(client, run_id).json()["run"]["status"] == "completed"
    assert [vid for vid, _ in gateway.updates] == ["a", "b", "c"]


def test_a_step_returns_only_log_lines_the_tab_does_not_have(client, gateway):
    run_id = apply_without_driving(client, gateway, ["a"])
    seen = client.get(f"/api/runs/{run_id}").json()["log"][-1]["id"]
    r = client.post(f"/api/runs/{run_id}/step?after_log_id={seen}", json={"driver": "tab-0000-test"},
                    headers=CLIENT_HEADERS).json()
    assert r["log"] and all(entry["id"] > seen for entry in r["log"])
    assert all("before" not in i and "after" not in i for i in r["items"])


def test_a_second_tab_cannot_drive_a_run_another_tab_is_driving(client, gateway, clock):
    run_id = apply_without_driving(client, gateway, ["a", "b"])
    gateway.after_update = lambda: clock.advance(STEP_BUDGET_S + 1)
    step(client, run_id, driver="tab-1111-first")

    r = step(client, run_id, driver="tab-2222-other")
    assert r.status_code == 409
    assert [vid for vid, _ in gateway.updates] == ["a"]
    progress = client.get(f"/api/runs/{run_id}/progress").json()  # the other tab watches instead
    assert progress["run"]["status"] == "running"


def test_a_run_nobody_drives_any_more_becomes_interrupted_and_needs_resume(client, gateway, clock):
    run_id = apply_without_driving(client, gateway, ["a", "b"])
    gateway.after_update = lambda: clock.advance(STEP_BUDGET_S + 1)
    step(client, run_id)  # a is written, then the tab is closed

    clock.advance(LEASE_S + 1)
    assert run_of(client, run_id) == ("interrupted", {"a": "success", "b": "pending"})
    assert step(client, run_id).status_code == 409  # never continues on its own (ADR-0007)
    assert [r["id"] for r in client.get("/api/runs?unfinished=true").json()] == [run_id]

    assert client.post(f"/api/runs/{run_id}/resume", json={"confirm_count": 1},
                       headers=CLIENT_HEADERS).status_code == 202
    assert drive(client, run_id).json()["run"]["status"] == "completed"
    assert [vid for vid, _ in gateway.updates] == ["a", "b"]


def test_a_run_applied_but_never_stepped_is_interrupted_once_its_lease_runs_out(client, gateway, clock):
    run_id = apply_without_driving(client, gateway, ["a"])
    clock.advance(LEASE_S + 1)
    assert run_of(client, run_id) == ("interrupted", {"a": "pending"})
    assert gateway.updates == []


def test_a_pause_asked_for_while_nobody_drives_takes_effect_when_the_lease_runs_out(client, gateway, clock):
    run_id = apply_without_driving(client, gateway, ["a", "b"])
    gateway.after_update = lambda: clock.advance(STEP_BUDGET_S + 1)
    step(client, run_id)
    assert client.post(f"/api/runs/{run_id}/pause", headers=CLIENT_HEADERS).status_code == 202

    clock.advance(LEASE_S + 1)
    assert run_of(client, run_id) == ("paused", {"a": "success", "b": "pending"})


def test_two_steps_at_once_never_write_the_same_run_even_from_the_same_tab(app, client, gateway):
    import pytest

    from app.runs import RunConflict

    run_id = apply_without_driving(client, gateway, ["a", "b"])
    refused = []

    def second_step_while_the_first_is_writing():
        with pytest.raises(RunConflict):
            app.state.runs.step(run_id, "tab-0000-test")  # a duplicated tab, or a double-mounted effect
        refused.append(True)

    gateway.after_update = second_step_while_the_first_is_writing
    assert drive(client, run_id).json()["run"]["status"] == "completed"
    assert refused == [True]
    assert [vid for vid, _ in gateway.updates] == ["a", "b"]


def test_a_step_that_outlived_its_lease_never_changes_the_run_afterwards(app, client, gateway, clock):
    runs = app.state.runs
    run_id = apply_without_driving(client, gateway, ["a"])  # a is the last Video, so the old Step would finish

    def lease_runs_out_and_the_owner_cancels():
        clock.advance(LEASE_S + 1)  # writing a took longer than the lease (long retries, say)
        assert runs.get(run_id)["status"] == "interrupted"
        runs.request(run_id, "cancel")

    gateway.after_update = lease_runs_out_and_the_owner_cancels
    step(client, run_id)  # the old Step then finishes its write and carries on

    assert run_of(client, run_id)[0] == "cancelled"  # not flipped to completed by the old Step


def test_a_step_that_outlived_its_lease_leaves_a_resumed_run_to_its_new_step(app, client, gateway, clock):
    runs = app.state.runs
    run_id = apply_without_driving(client, gateway, ["a", "b"])

    def lease_runs_out_and_the_owner_resumes():
        clock.advance(LEASE_S + 1)
        runs.get(run_id)
        runs.resume(run_id, confirm_count=2)

    gateway.after_update = lease_runs_out_and_the_owner_resumes
    step(client, run_id, driver="tab-1111-first")  # the old Step must stop, not write b

    assert [vid for vid, _ in gateway.updates] == ["a"]
    assert drive(client, run_id, driver="tab-2222-other").json()["run"]["status"] == "completed"
    assert [vid for vid, _ in gateway.updates] == ["a", "b"]  # a is recognised as already written
