from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS, make_client, sign_in

APPEND = {"type": "append", "text": "Footer"}


def setup(client, gateway, videos):
    gateway.videos = videos
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)


def create(client, operation, ids):
    return client.post("/api/changesets", json={"operation": operation, "video_ids": ids}, headers=CLIENT_HEADERS)


def patch(client, cs_id, video_id, body):
    return client.patch(f"/api/changesets/{cs_id}/items/{video_id}", json=body, headers=CLIENT_HEADERS)


def three_kinds(client, gateway):
    setup(client, gateway, [
        fake_video("change", title="Changes", description="Song"),
        fake_video("same", title="Same", description="Song\n\nFooter"),
        fake_video("big", title="Big", description="x" * 4999),
    ])
    return create(client, APPEND, ["change", "same", "big"])


def test_creating_a_changeset_proposes_every_selected_video(client, gateway):
    r = three_kinds(client, gateway)
    assert r.status_code == 201
    cs = r.json()
    assert cs["operation"] == {"type": "append", "text": "Footer", "separator": "blank_line", "skip_if_present": True}
    items = {i["video_id"]: i for i in cs["items"]}
    assert [i["video_id"] for i in cs["items"]] == ["change", "same", "big"]
    assert items["change"]["after"] == "Song\n\nFooter"
    assert (items["change"]["included"], items["same"]["included"], items["big"]["included"]) == (True, False, False)
    assert items["big"]["flags"][0]["code"] == "too_long"
    assert cs["counts"] == {"selected": 3, "to_write": 1, "excluded": 0, "unchanged": 1, "blocked": 1}


def test_a_changeset_can_be_read_back_after_a_restart(settings, provider, gateway):
    with make_client(settings, provider) as c:
        cs_id = three_kinds(c, gateway).json()["id"]
    with make_client(settings, provider) as c:
        r = c.get(f"/api/changesets/{cs_id}")
    assert r.status_code == 200
    assert r.json()["counts"]["to_write"] == 1


def test_excluding_and_including_a_video(client, gateway):
    cs = three_kinds(client, gateway).json()
    r = patch(client, cs["id"], "change", {"included": False})
    assert r.status_code == 200
    assert r.json()["item"]["included"] is False
    assert r.json()["counts"] == {"selected": 3, "to_write": 0, "excluded": 1, "unchanged": 1, "blocked": 1}
    assert patch(client, cs["id"], "change", {"included": True}).json()["counts"]["to_write"] == 1


def test_blocked_and_unchanged_videos_can_never_be_included(client, gateway):
    cs = three_kinds(client, gateway).json()
    blocked = patch(client, cs["id"], "big", {"included": True})
    unchanged = patch(client, cs["id"], "same", {"included": True})
    assert (blocked.status_code, unchanged.status_code) == (409, 409)
    assert "blocked" in blocked.json()["detail"].lower()
    assert client.get(f"/api/changesets/{cs['id']}").json()["counts"]["to_write"] == 1


def test_invalid_operations_never_reach_review(client, gateway):
    setup(client, gateway, [fake_video("a")])
    r = create(client, {"type": "template", "template": "{nope}"}, ["a"])
    assert r.status_code == 422
    assert "Unknown variable" in r.json()["detail"]


def test_unknown_changeset_or_item_is_404(client, gateway):
    cs = three_kinds(client, gateway).json()
    assert client.get("/api/changesets/999").status_code == 404
    assert patch(client, cs["id"], "nope", {"included": False}).status_code == 404


def test_a_new_changeset_replaces_the_previous_draft(client, gateway):
    first = three_kinds(client, gateway).json()
    second = create(client, APPEND, ["change"]).json()
    assert client.get(f"/api/changesets/{first['id']}").json()["status"] == "discarded"
    assert client.get(f"/api/changesets/{second['id']}").json()["status"] == "draft"
    assert patch(client, first["id"], "change", {"included": False}).status_code == 409


def test_empty_selection_is_rejected(client, gateway):
    setup(client, gateway, [fake_video("a")])
    assert create(client, APPEND, []).status_code == 422


def test_each_item_carries_its_bucket_and_the_review_carries_its_quota_cost(client, gateway):
    cs = three_kinds(client, gateway).json()
    assert {i["video_id"]: i["bucket"] for i in cs["items"]} == {
        "change": "to_write", "same": "unchanged", "big": "blocked"}
    assert cs["estimated_units"] == 50
    r = patch(client, cs["id"], "change", {"included": False})
    assert r.json()["item"]["bucket"] == "excluded"
    assert r.json()["estimated_units"] == 0


def test_selected_ids_that_are_no_longer_cached_are_reported(client, gateway):
    setup(client, gateway, [fake_video("a")])
    cs = create(client, APPEND, ["a", "gone", "a"]).json()
    assert cs["counts"]["selected"] == 1
    assert cs["missing"] == 1
