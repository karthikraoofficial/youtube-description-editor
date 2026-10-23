from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS, sign_in

APPEND = {"type": "append", "text": "Footer"}
SECTION = {"type": "section", "start_marker": "[L]", "end_marker": "[/L]", "content": "new"}


def setup(client, gateway, videos, op=APPEND):
    gateway.videos = videos
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)
    r = client.post("/api/changesets", json={"operation": op, "video_ids": [v.id for v in videos]},
                    headers=CLIENT_HEADERS)
    return r.json()["id"]


def patch(client, cs_id, video_id, body):
    return client.patch(f"/api/changesets/{cs_id}/items/{video_id}", json=body, headers=CLIENT_HEADERS)


def test_a_hand_edit_replaces_the_operations_result(client, gateway):
    cs = setup(client, gateway, [fake_video("a", description="Song")])
    r = patch(client, cs, "a", {"override": "Song\n\nMy own footer"})
    assert r.status_code == 200
    item = r.json()["item"]
    assert (item["after"], item["computed"], item["overridden"], item["bucket"]) == (
        "Song\n\nMy own footer", "Song\n\nFooter", True, "to_write")
    assert r.json()["overrides"] == 1


def test_a_hand_edit_is_revalidated_and_can_be_blocked(client, gateway):
    cs = setup(client, gateway, [fake_video("a", description="Song")])
    item = patch(client, cs, "a", {"override": "Song <b>bold</b>"}).json()["item"]
    assert item["bucket"] == "blocked"
    assert item["included"] is False
    assert [f["code"] for f in item["flags"]] == ["angle_brackets"]
    assert patch(client, cs, "a", {"included": True}).status_code == 409


def test_a_hand_edit_can_fix_a_blocked_video(client, gateway):
    cs = setup(client, gateway, [fake_video("a", description="[L] no end")], op=SECTION)
    item = patch(client, cs, "a", {"override": "[L]\nnew\n[/L]"}).json()["item"]
    assert (item["bucket"], item["included"], item["flags"]) == ("to_write", True, [])


def test_resetting_restores_the_operations_result_and_verdict(client, gateway):
    cs = setup(client, gateway, [fake_video("a", description="[L] no end")], op=SECTION)
    patch(client, cs, "a", {"override": "[L]\nnew\n[/L]"})
    r = patch(client, cs, "a", {"override": None})
    item = r.json()["item"]
    assert (item["after"], item["overridden"], item["bucket"]) == ("[L] no end", False, "blocked")
    assert item["flags"][0]["code"] == "markers_broken"
    assert r.json()["overrides"] == 0


def test_a_hand_edit_identical_to_the_current_text_is_unchanged(client, gateway):
    cs = setup(client, gateway, [fake_video("a", description="Song")])
    item = patch(client, cs, "a", {"override": "Song"}).json()["item"]
    assert (item["bucket"], item["included"]) == ("unchanged", False)


def test_hand_edits_survive_reading_the_review_back(client, gateway):
    cs = setup(client, gateway, [fake_video("a", description="Song"), fake_video("b", description="x")])
    patch(client, cs, "a", {"override": "Mine"})
    patch(client, cs, "b", {"included": False})
    body = client.get(f"/api/changesets/{cs}").json()
    assert (body["overrides"], body["counts"]["excluded"]) == (1, 1)
    assert body["items"][0]["after"] == "Mine"


def test_an_empty_patch_is_rejected(client, gateway):
    cs = setup(client, gateway, [fake_video("a")])
    assert patch(client, cs, "a", {}).status_code == 422


def test_the_open_review_can_be_found_after_a_reload(client, gateway):
    assert client.get("/api/changesets/open").json() is None
    cs = setup(client, gateway, [fake_video("a", description="Song")])
    assert client.get("/api/changesets/open").json() == {"id": cs}


def test_a_hand_edit_keeps_an_exclusion_the_owner_made(client, gateway):
    cs = setup(client, gateway, [fake_video("a", description="Song")])
    patch(client, cs, "a", {"included": False})
    assert patch(client, cs, "a", {"override": "Mine"}).json()["item"]["bucket"] == "excluded"
    assert patch(client, cs, "a", {"override": None}).json()["item"]["bucket"] == "excluded"


def test_a_hand_edit_equal_to_the_operations_result_is_not_an_override(client, gateway):
    cs = setup(client, gateway, [fake_video("a", description="Song")])
    r = patch(client, cs, "a", {"override": "Song\n\nFooter"}).json()
    assert (r["item"]["overridden"], r["overrides"]) == (False, 0)


def test_a_patch_with_only_nulls_does_nothing_and_is_rejected(client, gateway):
    cs = setup(client, gateway, [fake_video("a")])
    assert patch(client, cs, "a", {"included": None}).status_code == 422
