"""Pause and Cancel, through the HTTP seam."""
from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS, drive, sign_in


def click(app, action):
    """What the Pause/Cancel buttons call, fired from inside the Run (as a click mid-run would land)."""
    def hook():
        latest = app.state.runs.list()[0]["id"]
        app.state.runs.request(latest, action)
    return hook


def start(client, gateway, ids, after_first_write=None):
    gateway.videos = [fake_video(v, description="Song") for v in ids]
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)
    cs = client.post("/api/changesets", json={"operation": {"type": "append", "text": "Footer"}, "video_ids": ids},
                     headers=CLIENT_HEADERS).json()
    gateway.after_update = after_first_write
    run_id = client.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": len(ids)},
                         headers=CLIENT_HEADERS).json()["id"]
    drive(client, run_id)
    return run_id


def run_of(client, run_id):
    r = client.get(f"/api/runs/{run_id}").json()
    return r["status"], {i["video_id"]: i["status"] for i in r["items"]}


def control(client, run_id, action):
    return client.post(f"/api/runs/{run_id}/{action}", headers=CLIENT_HEADERS)


def test_pause_stops_after_the_current_video_and_resume_carries_on(app, client, gateway, sleeps):
    run_id = start(client, gateway, ["a", "b", "c"], after_first_write=click(app, "pause"))
    status, items = run_of(client, run_id)
    assert (status, items) == ("paused", {"a": "success", "b": "pending", "c": "pending"})
    assert [vid for vid, _ in gateway.updates] == ["a"]

    client.post(f"/api/runs/{run_id}/resume", json={"confirm_count": 2}, headers=CLIENT_HEADERS)
    drive(client, run_id)
    assert run_of(client, run_id) == ("completed", {"a": "success", "b": "success", "c": "success"})


def test_cancel_stops_and_marks_the_rest_cancelled_for_good(app, client, gateway, sleeps):
    run_id = start(client, gateway, ["a", "b", "c"], after_first_write=click(app, "cancel"))
    assert run_of(client, run_id) == ("cancelled", {"a": "success", "b": "cancelled", "c": "cancelled"})
    assert client.post(f"/api/runs/{run_id}/resume", json={"confirm_count": 0},
                       headers=CLIENT_HEADERS).status_code == 409


def test_a_paused_run_can_be_cancelled_directly(app, client, gateway, sleeps):
    run_id = start(client, gateway, ["a", "b"], after_first_write=click(app, "pause"))
    assert control(client, run_id, "cancel").status_code == 202
    assert run_of(client, run_id) == ("cancelled", {"a": "success", "b": "cancelled"})


def test_pausing_a_finished_run_is_refused(client, gateway, sleeps):
    run_id = start(client, gateway, ["a"])
    assert control(client, run_id, "pause").status_code == 409
    assert control(client, run_id, "cancel").status_code == 409


def test_a_cancel_survives_the_run_stopping_for_another_reason(app, client, gateway, sleeps):
    from app.youtube.errors import QuotaExceeded

    def cancel_during_the_write():
        click(app, "cancel")()  # the owner clicks Cancel while b is being written…
        return QuotaExceeded("quotaExceeded")  # …and that write then hits the quota stop

    gateway.fail_updates["b"] = cancel_during_the_write
    run_id = start(client, gateway, ["a", "b", "c"])
    assert run_of(client, run_id) == ("cancelled", {"a": "success", "b": "cancelled", "c": "cancelled"})
