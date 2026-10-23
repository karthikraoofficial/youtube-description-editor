"""The JSON copy of each Run's Backups goes to an archive: local files, or a private Vercel Blob store (ADR-0018)."""
import json

import pytest
from fastapi.testclient import TestClient

from app.backups import BackupArchiveError, BlobArchive
from app.main import create_app
from app.shorts import FakeShortsProber
from app.youtube.errors import QuotaExceeded
from app.youtube.fake import fake_video

from .conftest import BASE_URL, CLIENT_HEADERS, drive, sign_in


class MemoryArchive:
    def __init__(self, fail: bool = False) -> None:
        self.saved: dict[int, dict] = {}
        self.fail = fail

    def save(self, run_id: int, document: dict) -> None:
        if self.fail:
            raise BackupArchiveError("Blob store unavailable")
        self.saved[run_id] = json.loads(json.dumps(document))  # what would be stored, not a live reference


def client_with(settings, provider, clock, archive):
    app = create_app(settings, provider=provider, prober=FakeShortsProber(default=False), clock=clock, archive=archive)
    return TestClient(app, base_url=BASE_URL)


def apply(client, gateway, videos):
    gateway.videos = videos
    sign_in(client)
    client.post("/api/sync", headers=CLIENT_HEADERS)
    cs = client.post("/api/changesets", json={"operation": {"type": "append", "text": "Footer"},
                                              "video_ids": [v.id for v in videos]}, headers=CLIENT_HEADERS).json()
    run_id = client.post(f"/api/changesets/{cs['id']}/apply", json={"confirm_count": len(videos)},
                         headers=CLIENT_HEADERS).json()["id"]
    return run_id, drive(client, run_id).json()


def test_if_the_backup_copy_cannot_be_saved_nothing_is_written(settings, provider, gateway, clock):
    with client_with(settings, provider, clock, MemoryArchive(fail=True)) as client:
        run_id, progress = apply(client, gateway, [fake_video("a", description="Song")])
        assert progress["run"]["status"] == "paused"
        assert {i["video_id"]: i["status"] for i in progress["items"]} == {"a": "pending"}
        assert gateway.updates == []
        log = [entry["message"] for entry in client.get(f"/api/runs/{run_id}").json()["log"]]
    assert any("backup copy" in message and "Nothing was written" in message for message in log)


def test_the_copy_keeps_each_videos_first_backup_when_a_run_is_resumed(settings, provider, gateway, clock, sleeps):
    archive = MemoryArchive()
    with client_with(settings, provider, clock, archive) as client:
        gateway.fail_updates["b"] = [QuotaExceeded("quotaExceeded")]
        run_id, progress = apply(client, gateway, [fake_video("a", description="One"),
                                                   fake_video("b", description="Two")])
        assert progress["run"]["status"] == "paused_quota"
        gateway.set_description("b", "Two, edited in Studio")  # the next fetch sees this text
        client.post(f"/api/runs/{run_id}/resume", json={"confirm_count": 1}, headers=CLIENT_HEADERS)
        drive(client, run_id)

    saved = {v["video_id"]: v["snippet"]["description"] for v in archive.saved[run_id]["videos"]}
    assert saved == {"a": "One", "b": "Two"}


def test_the_blob_archive_uploads_one_private_file_per_run_and_overwrites_it():
    calls = []
    archive = BlobArchive(put=lambda pathname, body, **options: calls.append((pathname, body, options)))
    archive.save(7, {"run_id": 7, "videos": [{"video_id": "a", "snippet": {"description": "Ünïcode"}}]})

    pathname, body, options = calls[0]
    assert pathname == "backups/run-7.json"
    assert json.loads(body.decode("utf-8"))["videos"][0]["snippet"]["description"] == "Ünïcode"
    assert options == {"access": "private", "allow_overwrite": True, "content_type": "application/json"}


def test_a_failed_blob_upload_is_reported_as_an_archive_error():
    def put(*_args, **_kwargs):
        raise OSError("connection reset")

    with pytest.raises(BackupArchiveError):
        BlobArchive(put=put).save(7, {"run_id": 7, "videos": []})
