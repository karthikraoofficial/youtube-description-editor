"""The Field a Changeset edits (ADR-0022), through the HTTP seam with the fake YouTube."""
from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS, drive, sign_in

APPEND = {"type": "append", "text": "Footer"}


def synced(client, gateway, videos):
    gateway.videos = videos
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)


def create(client, ids, op=APPEND, **extra):
    return client.post("/api/changesets", json={"operation": op, "video_ids": ids, **extra}, headers=CLIENT_HEADERS)


def test_a_changeset_edits_the_description_unless_told_otherwise(client, gateway):
    synced(client, gateway, [fake_video("a", description="One")])
    implicit = create(client, ["a"]).json()
    explicit = create(client, ["a"], field="description").json()
    assert (implicit["field"], explicit["field"]) == ("description", "description")
    assert explicit["items"][0]["after"] == "One\n\nFooter"
    for path in ("/api/preview", "/api/preview/summary"):
        r = client.post(path, json={"operation": APPEND, "video_ids": ["a"]}, headers=CLIENT_HEADERS)
        assert r.json()["field"] == "description", path


def test_an_unknown_field_is_refused_and_nothing_is_saved(client, gateway):
    synced(client, gateway, [fake_video("a", description="One")])
    for path in ("/api/preview", "/api/preview/summary", "/api/changesets"):
        r = client.post(path, json={"operation": APPEND, "video_ids": ["a"], "field": "category"},
                        headers=CLIENT_HEADERS)
        assert r.status_code == 422, path
    assert client.get("/api/changesets/open").json() is None


def test_runs_restores_and_history_say_which_field_they_edited(client, gateway, sleeps):
    synced(client, gateway, [fake_video("a", description="One")])
    cs = create(client, ["a"]).json()
    run_id = client.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": 1},
                         headers=CLIENT_HEADERS).json()["id"]
    drive(client, run_id)
    restore_id = client.post(f"/api/runs/{run_id}/restore", json={"confirm_count": 1},
                             headers=CLIENT_HEADERS).json()["id"]
    drive(client, restore_id)
    assert client.get(f"/api/runs/{run_id}").json()["field"] == "description"
    assert client.get(f"/api/runs/{restore_id}").json()["field"] == "description"
    assert {r["id"]: r["field"] for r in client.get("/api/runs").json()} == {
        run_id: "description", restore_id: "description"}
    assert gateway.description_of("a") == "One"


def test_the_fields_the_app_can_edit_are_served_from_the_one_registry(client):
    """The Edit screen reads what each Field allows from here, never from its own copy (ADR-0001, ADR-0022)."""
    fields = {f["field"]: f for f in client.get("/api/fields").json()}
    assert list(fields) == ["description", "title"]
    assert fields["title"] == {
        "field": "title", "label": "Title", "singular": "title", "plural": "titles", "one_line": True,
        "operations": ["find_replace", "append", "prepend"], "separators": ["pipe", "dash", "space", "none"],
        "max_size": 100, "size_unit": "characters"}
    assert fields["description"]["operations"] == ["find_replace", "append", "prepend", "template", "section"]
    assert fields["description"]["separators"] == ["blank_line", "newline", "none"]
