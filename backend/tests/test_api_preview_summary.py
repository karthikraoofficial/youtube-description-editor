from app.youtube.fake import fake_video

from .conftest import CLIENT_HEADERS


def setup(client, gateway, videos):
    gateway.videos = videos
    client.post("/api/auth/connect", headers=CLIENT_HEADERS)
    client.post("/api/sync", headers=CLIENT_HEADERS)


def summary(client, operation, ids):
    return client.post("/api/preview/summary", json={"operation": operation, "video_ids": ids},
                       headers=CLIENT_HEADERS)


def test_summary_covers_every_selected_video_not_just_the_sample(client, gateway):
    footer = "Lessons: https://example.com"
    videos = [fake_video(f"v{i:02}", description="Song") for i in range(30)]
    videos.append(fake_video("near_limit", description="x" * 4990))
    videos.append(fake_video("has_footer", description=f"Song\n\n{footer}"))
    setup(client, gateway, videos)

    op = {"type": "append", "text": footer, "skip_if_present": True}
    r = summary(client, op, [v.id for v in videos])

    assert r.status_code == 200
    # The three buckets never overlap: 30 + 1 + 1 = 32.
    assert r.json() == {"selected": 32, "changed": 30, "unchanged": 1, "blocked": 1,
                        "largest_after_bytes": 5020, "max_bytes": 5000}


def test_summary_reports_operation_errors_like_preview(client, gateway):
    setup(client, gateway, [fake_video("a")])
    r = summary(client, {"type": "find_replace", "find": "(", "replace": "", "regex": True}, ["a"])
    assert r.status_code == 422


def test_summary_gives_up_cleanly_when_it_takes_too_long(client, gateway, monkeypatch):
    import app.api.preview as preview_api

    monkeypatch.setattr(preview_api, "SUMMARY_BUDGET_S", 0)
    setup(client, gateway, [fake_video("a"), fake_video("b")])
    r = summary(client, {"type": "append", "text": "x"}, ["a", "b"])
    assert r.status_code == 422
    assert "too long" in r.json()["detail"]


def test_videos_with_broken_markers_count_as_blocked(client, gateway):
    setup(client, gateway, [fake_video("ok", description="[L]\nold\n[/L]"),
                            fake_video("broken", description="[L] but no end")])
    op = {"type": "section", "start_marker": "[L]", "end_marker": "[/L]", "content": "new"}
    s = summary(client, op, ["ok", "broken"]).json()
    assert (s["changed"], s["unchanged"], s["blocked"]) == (1, 0, 1)
