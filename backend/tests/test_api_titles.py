"""Bulk-editing titles (ADR-0022), end to end through the HTTP seam with the fake YouTube."""
from dataclasses import replace

from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS, drive, sign_in

PIPE_GUITAR = {"type": "append", "text": "Guitar", "separator": "pipe"}


def synced(client, gateway, videos):
    gateway.videos = videos
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)


def preview(client, op, ids):
    return client.post("/api/preview", json={"operation": op, "video_ids": ids, "field": "title"},
                       headers=CLIENT_HEADERS)


def review(client, op, ids):
    return client.post("/api/changesets", json={"operation": op, "video_ids": ids, "field": "title"},
                       headers=CLIENT_HEADERS)


def apply(client, cs):
    r = client.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": cs["counts"]["to_write"]},
                    headers=CLIENT_HEADERS)
    assert r.status_code == 202, r.text
    drive(client, r.json()["id"])
    return r.json()["id"]


def test_appending_to_titles_previews_each_new_title_and_its_length(client, gateway):
    synced(client, gateway, [fake_video("a", title="Song One", description="Keep me")])
    r = preview(client, PIPE_GUITAR, ["a"]).json()
    item = r["items"][0]
    assert (item["before"], item["after"], item["changed"]) == ("Song One", "Song One | Guitar", True)
    assert (item["after_size"], r["max_size"], r["size_unit"]) == (17, 100, "characters")


def test_a_title_that_already_ends_with_the_text_is_left_alone(client, gateway):
    synced(client, gateway, [fake_video("a", title="Song One | Guitar")])
    assert preview(client, PIPE_GUITAR, ["a"]).json()["items"][0]["changed"] is False


def test_prepend_and_find_replace_work_on_titles(client, gateway):
    synced(client, gateway, [fake_video("a", title="Song One (live)")])
    prepend = preview(client, {"type": "prepend", "text": "Late Night", "separator": "dash"}, ["a"]).json()
    replaced = preview(client, {"type": "find_replace", "find": "(live)", "replace": "[Live]"}, ["a"]).json()
    assert prepend["items"][0]["after"] == "Late Night - Song One (live)"
    assert replaced["items"][0]["after"] == "Song One [Live]"


def test_titles_youtube_would_refuse_are_blocked(client, gateway):
    synced(client, gateway, [fake_video("long", title="x" * 95), fake_video("empty", title="Remove me"),
                             fake_video("brackets", title="Song")])
    long = preview(client, {"type": "append", "text": "y" * 10, "separator": "space"}, ["long"]).json()["items"][0]
    empty = preview(client, {"type": "find_replace", "find": "Remove me"}, ["empty"]).json()["items"][0]
    brackets = preview(client, {"type": "append", "text": "<3", "separator": "space"}, ["brackets"]).json()["items"][0]
    assert [f["code"] for f in long["flags"]] == ["too_long"] and long["flags"][0]["blocking"]
    assert [f["code"] for f in empty["flags"]] == ["empty"]
    assert [f["code"] for f in brackets["flags"]] == ["angle_brackets"]


def test_operations_that_only_make_sense_for_descriptions_are_refused_for_titles(client, gateway):
    synced(client, gateway, [fake_video("a", title="Song")])
    for op in ({"type": "template", "template": "{title} live"},
               {"type": "section", "start_marker": "[a]", "end_marker": "[/a]"},
               {"type": "append", "text": "Guitar", "separator": "blank_line"}):
        assert preview(client, op, ["a"]).status_code == 422, op
        assert review(client, op, ["a"]).status_code == 422, op
    assert client.get("/api/changesets/open").json() is None


def test_applying_writes_only_the_title_and_updates_the_cache(client, gateway, sleeps):
    synced(client, gateway, [fake_video("a", title="Song", description="Keep me", tags=("x",))])
    cs = review(client, PIPE_GUITAR, ["a"]).json()
    run_id = apply(client, cs)
    video_id, body = gateway.updates[-1]
    assert (video_id, body["title"], body["description"], body["tags"]) == ("a", "Song | Guitar", "Keep me", ["x"])
    assert client.get("/api/videos").json()[0]["title"] == "Song | Guitar"
    run = client.get(f"/api/runs/{run_id}").json()
    assert (run["field"], run["counts"]["success"]) == ("title", 1)
    assert client.get("/api/runs").json()[0]["operation_summary"] == 'Append to Title: "Guitar"'


def test_a_title_changed_in_studio_since_the_review_is_skipped(client, gateway, sleeps):
    synced(client, gateway, [fake_video("a", title="Song")])
    cs = review(client, PIPE_GUITAR, ["a"]).json()
    gateway.videos = [replace(v, title="Renamed in Studio") for v in gateway.videos]
    run_id = apply(client, cs)
    assert client.get(f"/api/runs/{run_id}").json()["items"][0]["status"] == "stale"
    assert gateway.videos[0].title == "Renamed in Studio"


def test_restoring_puts_the_old_title_back_and_keeps_todays_description(client, gateway, sleeps):
    synced(client, gateway, [fake_video("a", title="Song", description="One")])
    run_id = apply(client, review(client, PIPE_GUITAR, ["a"]).json())
    gateway.set_description("a", "Edited in Studio")
    restore_id = client.post(f"/api/runs/{run_id}/restore", json={"confirm_count": 1},
                             headers=CLIENT_HEADERS).json()["id"]
    drive(client, restore_id)
    assert (gateway.videos[0].title, gateway.videos[0].description) == ("Song", "Edited in Studio")
    assert client.get(f"/api/runs/{restore_id}").json()["field"] == "title"


def test_a_hand_edited_title_is_checked_like_any_other(client, gateway):
    synced(client, gateway, [fake_video("a", title="Song")])
    cs = review(client, PIPE_GUITAR, ["a"]).json()
    for override, code in (("z" * 101, "too_long"), ("Two\nlines", "line_break")):
        r = client.patch(f"/api/changesets/{cs['id']}/items/a", json={"override": override}, headers=CLIENT_HEADERS)
        item = r.json()["item"]
        assert (item["bucket"], [f["code"] for f in item["flags"]]) == ("blocked", [code]), override


def test_find_and_replace_on_titles_takes_regular_expressions(client, gateway):
    synced(client, gateway, [fake_video("a", title="Track 7 (2019 remaster)")])
    op = {"type": "find_replace", "find": r"\s*\(\d{4} remaster\)", "replace": "", "regex": True}
    assert preview(client, op, ["a"]).json()["items"][0]["after"] == "Track 7"
