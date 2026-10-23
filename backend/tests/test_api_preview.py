from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS, sign_in

FIND_OLD = {"type": "find_replace", "find": "old.link", "replace": "new.link"}


def setup(client, gateway, videos):
    gateway.videos = videos
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)


def preview(client, operation, ids):
    return client.post("/api/preview", json={"operation": operation, "video_ids": ids}, headers=CLIENT_HEADERS)


def test_preview_shows_before_after_and_flags(client, gateway):
    setup(client, gateway, [
        fake_video("a", title="A", description="Listen: old.link"),
        fake_video("b", title="B", description="nothing here"),
        fake_video("c", title="C", description="old.link " + "x" * 4995),
    ])
    r = preview(client, FIND_OLD, ["a", "b", "c"])

    assert r.status_code == 200
    items = {i["video_id"]: i for i in r.json()["items"]}
    assert items["a"] == {"video_id": "a", "title": "A", "before": "Listen: old.link", "after": "Listen: new.link",
                          "changed": True, "after_bytes": 16, "flags": []}
    assert items["b"]["changed"] is False
    assert items["c"]["flags"] == [{"code": "too_long", "blocking": True,
                                    "message": "5,004 bytes: 4 over YouTube's 5,000-byte limit."}]


def test_preview_keeps_the_requested_order_and_skips_unknown_ids(client, gateway):
    setup(client, gateway, [fake_video("a"), fake_video("b")])
    r = preview(client, FIND_OLD, ["b", "missing", "a"])
    assert [i["video_id"] for i in r.json()["items"]] == ["b", "a"]


def test_a_bad_operation_is_a_422_with_a_readable_message(client, gateway):
    setup(client, gateway, [fake_video("a")])
    r = preview(client, {"type": "find_replace", "find": "(", "replace": "", "regex": True}, ["a"])
    assert r.status_code == 422
    assert "Invalid regular expression" in r.json()["detail"]


def test_unknown_operation_type_is_rejected(client, gateway):
    setup(client, gateway, [fake_video("a")])
    assert preview(client, {"type": "delete_everything"}, ["a"]).status_code == 422


def test_preview_is_capped_to_a_sample(client, gateway):
    setup(client, gateway, [fake_video(f"v{i}") for i in range(30)])
    r = preview(client, FIND_OLD, [f"v{i}" for i in range(30)])
    assert len(r.json()["items"]) == 20


def test_template_variables_are_listed_for_the_builder(client):
    r = client.get("/api/template-variables")
    assert r.status_code == 200
    assert r.json()[0] == {"name": "description", "help": "the current description"}
    assert {"title", "video_url", "publish_date", "duration"} <= {v["name"] for v in r.json()}


def test_template_preview_says_whether_the_description_is_kept(client, gateway):
    setup(client, gateway, [fake_video("a")])
    kept = preview(client, {"type": "template", "template": "{ description }\n\n{title}"}, ["a"]).json()
    dropped = preview(client, {"type": "template", "template": "{{description}} {title}"}, ["a"]).json()
    other = preview(client, FIND_OLD, ["a"]).json()
    assert (kept["keeps_description"], dropped["keeps_description"], other["keeps_description"]) == (True, False, None)


def test_template_preview_reports_unknown_variables(client, gateway):
    setup(client, gateway, [fake_video("a")])
    r = preview(client, {"type": "template", "template": "{nope}"}, ["a"])
    assert r.status_code == 422
    assert "Unknown variable {nope}" in r.json()["detail"]
