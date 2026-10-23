"""Bulk-editing tags (ADR-0022), end to end through the HTTP seam with the fake YouTube. Tags travel as text, one
tag per line, and go back to YouTube as a list."""
from dataclasses import replace

from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS, drive, sign_in


def synced(client, gateway, videos):
    gateway.videos = videos
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)


def preview(client, op, ids):
    return client.post("/api/preview", json={"operation": op, "video_ids": ids, "field": "tags"},
                       headers=CLIENT_HEADERS)


def review(client, op, ids):
    return client.post("/api/changesets", json={"operation": op, "video_ids": ids, "field": "tags"},
                       headers=CLIENT_HEADERS)


def apply(client, cs):
    r = client.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": cs["counts"]["to_write"]},
                    headers=CLIENT_HEADERS)
    assert r.status_code == 202, r.text
    drive(client, r.json()["id"])
    return r.json()["id"]


def test_adding_tags_skips_ones_a_video_already_has_in_any_case(client, gateway):
    synced(client, gateway, [fake_video("a", tags=("Music", "live"))])
    r = preview(client, {"type": "add_tags", "tags": ["music", "guitar", "Guitar"]}, ["a"]).json()
    item = r["items"][0]
    assert (item["before"], item["after"]) == ("Music\nlive", "Music\nlive\nguitar")
    assert (r["max_size"], r["size_unit"]) == (500, "characters")


def test_a_video_that_already_has_every_tag_is_unchanged(client, gateway):
    synced(client, gateway, [fake_video("a", tags=("guitar",))])
    assert preview(client, {"type": "add_tags", "tags": ["GUITAR"]}, ["a"]).json()["items"][0]["changed"] is False


def test_removing_tags_matches_in_any_case(client, gateway):
    synced(client, gateway, [fake_video("a", tags=("Old Tour", "music", "old tour 2019"))])
    item = preview(client, {"type": "remove_tags", "tags": ["old tour"]}, ["a"]).json()["items"][0]
    assert item["after"] == "music\nold tour 2019"


def test_find_and_replace_renames_a_tag_and_merges_duplicates(client, gateway):
    synced(client, gateway, [fake_video("a", tags=("lofi", "lo-fi", "music"))])
    item = preview(client, {"type": "find_replace", "find": "lo-fi", "replace": "lofi"}, ["a"]).json()["items"][0]
    assert item["after"] == "lofi\nmusic"


def test_tags_over_youtubes_limit_are_blocked_counted_as_youtube_counts(client, gateway):
    # 24 tags of 19 characters with a space: each counts 19 + 2 quotes, plus a comma between each = 527.
    synced(client, gateway, [fake_video("a")])
    many = [f"tag number {i:02} xyzab" for i in range(24)]
    item = preview(client, {"type": "add_tags", "tags": many}, ["a"]).json()["items"][0]
    assert item["after_size"] == 24 * 21 + 23
    assert [f["code"] for f in item["flags"]] == ["too_long"]


def test_operations_for_other_fields_are_refused_for_tags_and_tag_operations_elsewhere(client, gateway):
    synced(client, gateway, [fake_video("a", tags=("x",))])
    for op in ({"type": "append", "text": "x", "separator": "none"}, {"type": "template", "template": "x"}):
        assert preview(client, op, ["a"]).status_code == 422, op
    r = client.post("/api/preview", json={"operation": {"type": "add_tags", "tags": ["x"]}, "video_ids": ["a"],
                                          "field": "title"}, headers=CLIENT_HEADERS)
    assert r.status_code == 422


def test_applying_writes_only_the_tags_as_a_list(client, gateway, sleeps):
    synced(client, gateway, [fake_video("a", title="Song", description="Keep me", tags=("music",))])
    run_id = apply(client, review(client, {"type": "add_tags", "tags": ["guitar", "live"]}, ["a"]).json())
    _, body = gateway.updates[-1]
    assert (body["tags"], body["title"], body["description"]) == (["music", "guitar", "live"], "Song", "Keep me")
    assert client.get("/api/videos").json()[0]["tags"] == ["music", "guitar", "live"]
    assert client.get("/api/runs").json()[0]["operation_summary"] == 'Add tags: "guitar, live"'
    assert client.get(f"/api/runs/{run_id}").json()["field"] == "tags"


def test_removing_every_tag_leaves_the_video_without_tags(client, gateway, sleeps):
    synced(client, gateway, [fake_video("a", tags=("old",))])
    apply(client, review(client, {"type": "remove_tags", "tags": ["old"]}, ["a"]).json())
    _, body = gateway.updates[-1]
    assert body.get("tags", []) == [] and gateway.videos[0].tags == ()


def test_tags_changed_in_studio_since_the_review_are_skipped(client, gateway, sleeps):
    synced(client, gateway, [fake_video("a", tags=("music",))])
    cs = review(client, {"type": "add_tags", "tags": ["guitar"]}, ["a"]).json()
    gateway.videos = [replace(v, tags=("music", "added in studio")) for v in gateway.videos]
    run_id = apply(client, cs)
    assert client.get(f"/api/runs/{run_id}").json()["items"][0]["status"] == "stale"


def test_restoring_puts_back_the_exact_tag_list(client, gateway, sleeps):
    synced(client, gateway, [fake_video("a", tags=("B", "a", "c"))])
    run_id = apply(client, review(client, {"type": "remove_tags", "tags": ["a"]}, ["a"]).json())
    restore_id = client.post(f"/api/runs/{run_id}/restore", json={"confirm_count": 1},
                             headers=CLIENT_HEADERS).json()["id"]
    drive(client, restore_id)
    assert gateway.videos[0].tags == ("B", "a", "c")


def test_hand_edited_tags_are_one_per_line_and_checked(client, gateway):
    synced(client, gateway, [fake_video("a", tags=("music",))])
    cs = review(client, {"type": "add_tags", "tags": ["guitar"]}, ["a"]).json()
    ok = client.patch(f"/api/changesets/{cs['id']}/items/a", json={"override": "music\nacoustic"},
                      headers=CLIENT_HEADERS).json()["item"]
    bad = client.patch(f"/api/changesets/{cs['id']}/items/a", json={"override": "music\n<b>"},
                       headers=CLIENT_HEADERS).json()["item"]
    assert (ok["bucket"], bad["bucket"]) == ("to_write", "blocked")


def test_find_and_replace_runs_on_each_tag_on_its_own(client, gateway):
    # On the joined text, \s+ would also eat the line break between tags and merge them.
    synced(client, gateway, [fake_video("a", tags=("late night", "music"))])
    op = {"type": "find_replace", "find": r"\s+", "replace": "-", "regex": True}
    assert preview(client, op, ["a"]).json()["items"][0]["after"] == "late-night\nmusic"


def test_the_write_differs_from_the_fresh_snippet_only_in_tags(client, gateway, sleeps):
    from app.youtube.fake import _snippet_of
    from app.runs import WRITABLE_FIELDS

    video = fake_video("a", tags=("music",), default_language="en", default_audio_language="en-US")
    synced(client, gateway, [video])
    apply(client, review(client, {"type": "add_tags", "tags": ["guitar"]}, ["a"]).json())
    # Empty optional fields are left out, as for every Field (ADR-0002).
    fresh = {k: v for k, v in _snippet_of(video).items() if k in WRITABLE_FIELDS and v not in (None, [], "")}
    assert gateway.updates[-1][1] == {**fresh, "tags": ["music", "guitar"]}


def test_restore_puts_back_a_tag_list_exactly_even_with_repeats(client, gateway, sleeps):
    synced(client, gateway, [fake_video("a", tags=("Music", "music", "old"))])
    run_id = apply(client, review(client, {"type": "remove_tags", "tags": ["old"]}, ["a"]).json())
    assert gateway.videos[0].tags == ("Music",)  # a change tidies the list
    restore_id = client.post(f"/api/runs/{run_id}/restore", json={"confirm_count": 1},
                             headers=CLIENT_HEADERS).json()["id"]
    drive(client, restore_id)
    assert gateway.videos[0].tags == ("Music", "music", "old")


def test_an_operation_that_changes_nothing_leaves_untidy_tags_alone(client, gateway):
    synced(client, gateway, [fake_video("a", tags=("Music", "music"))])
    assert preview(client, {"type": "remove_tags", "tags": ["absent"]}, ["a"]).json()["items"][0]["changed"] is False


def test_a_tag_containing_a_comma_is_blocked(client, gateway):
    synced(client, gateway, [fake_video("a", tags=("rock",))])
    item = preview(client, {"type": "find_replace", "find": "rock", "replace": "rock, roll"}, ["a"]).json()["items"][0]
    assert [f["code"] for f in item["flags"]] == ["comma"]


def test_find_and_replace_on_tags_reads_well_in_history(client, gateway, sleeps):
    synced(client, gateway, [fake_video("a", tags=("lo-fi",))])
    apply(client, review(client, {"type": "find_replace", "find": "lo-fi", "replace": "lofi"}, ["a"]).json())
    assert client.get("/api/runs").json()[0]["operation_summary"] == 'Replace "lo-fi" with "lofi" in tags'
