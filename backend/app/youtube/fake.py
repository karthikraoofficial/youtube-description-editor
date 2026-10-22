"""In-memory YouTube used by tests and `python dev.py --fake`. Never talks to Google."""
import threading
from dataclasses import replace
from pathlib import Path

from app.youtube.errors import AuthExpired, GatewayError
from app.youtube.gateway import Channel, FreshSnippet, UploadsPage, VideoDetails

FAKE_CHANNEL = Channel(id="UC_fake_channel", title="Fake Channel", avatar_url=None,
                       uploads_playlist_id="UU_fake_channel")


def fake_video(video_id: str, *, title: str | None = None, description: str = "",
               published_at: str = "2025-01-01T00:00:00Z", duration_s: int = 300,
               privacy_status: str = "public", tags: tuple[str, ...] = (), category_id: str = "10",
               default_language: str | None = None, default_audio_language: str | None = None) -> VideoDetails:
    return VideoDetails(
        id=video_id, title=title or f"Video {video_id}", description=description, category_id=category_id,
        tags=tags, default_language=default_language, default_audio_language=default_audio_language,
        published_at=published_at, duration_s=duration_s, privacy_status=privacy_status,
        thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg")


def _snippet_of(v: VideoDetails) -> dict:
    """What YouTube's snippet looks like, including read-only fields an update must not send back."""
    snippet = {"publishedAt": v.published_at, "channelId": "UC_fake_channel", "title": v.title,
               "description": v.description, "thumbnails": {"medium": {"url": v.thumbnail_url}},
               "channelTitle": "Fake Channel", "categoryId": v.category_id, "liveBroadcastContent": "none",
               "localized": {"title": v.title, "description": v.description}}
    if v.tags:
        snippet["tags"] = list(v.tags)
    if v.default_language:
        snippet["defaultLanguage"] = v.default_language
    if v.default_audio_language:
        snippet["defaultAudioLanguage"] = v.default_audio_language
    return snippet


def sample_videos() -> list[VideoDetails]:
    """A believable channel for --fake mode: long videos, Shorts, and a few non-public uploads."""
    links = "\n\nListen everywhere: https://example.com/listen\nInstagram: @fakechannel"
    videos = []
    for i in range(1, 31):
        short = i % 4 == 0
        videos.append(fake_video(
            f"fake{i:03}",
            title=f"{'#Shorts ' if short else ''}Track {i}: Late Night Session",
            description=f"Track {i} from the Late Night Sessions.{links}",
            published_at=f"2025-{(i % 12) + 1:02}-{(i % 27) + 1:02}T18:00:00Z",
            duration_s=40 + i if short else 180 + i * 7,
            privacy_status="unlisted" if i % 10 == 0 else "private" if i % 13 == 0 else "public",
            tags=("music", "late night"), default_language="en"))
    return videos


class FakeGateway:
    def __init__(self, channel: Channel = FAKE_CHANNEL, *, page_size: int = 50) -> None:
        self.channel = channel
        self.videos: list[VideoDetails] = []  # every upload, in uploads-playlist order
        self.page_size = page_size
        self.calls: list[str] = []  # API method names, in call order
        self.fail_with: Exception | None = None  # raised by every call while set
        # video_id -> the error its update raises, or a list raised one per attempt (then it succeeds)
        self.fail_updates: dict[str, Exception | list[Exception]] = {}
        self.fail_snippet_calls: list[Exception] = []  # raised one per get_snippets call, in order
        self.updates: list[tuple[str, dict]] = []  # (video_id, snippet body) for every successful update
        self.check_backups_in: Path | None = None  # if set, the first update checks a backup file exists
        self.backup_seen_at_first_write: bool | None = None

    def _call(self, method: str) -> None:
        self.calls.append(method)
        if self.fail_with:
            raise self.fail_with

    def get_my_channel(self) -> Channel:
        self._call("channels.list")
        return self.channel

    def list_uploads_page(self, playlist_id: str, page_token: str | None) -> UploadsPage:
        self._call("playlistItems.list")
        start = int(page_token or 0)
        ids = [v.id for v in self.videos[start:start + self.page_size]]
        nxt = start + self.page_size
        return UploadsPage(ids, str(nxt) if nxt < len(self.videos) else None)

    def get_videos(self, video_ids: list[str]) -> list[VideoDetails]:
        self._call("videos.list")
        assert len(video_ids) <= 50, "videos.list accepts at most 50 ids"
        wanted = set(video_ids)
        return [v for v in self.videos if v.id in wanted]

    # --- writes (tests inspect self.updates; nothing here talks to Google) ---------------------

    def get_snippets(self, video_ids: list[str]) -> list[FreshSnippet]:
        self._call("videos.list")
        if self.fail_snippet_calls:
            raise self.fail_snippet_calls.pop(0)
        assert len(video_ids) <= 50, "videos.list accepts at most 50 ids"
        wanted = set(video_ids)
        return [FreshSnippet(v.id, _snippet_of(v), v.privacy_status) for v in self.videos if v.id in wanted]

    def update_snippet(self, video_id: str, snippet: dict) -> None:
        if self.check_backups_in is not None and not self.updates:
            self.backup_seen_at_first_write = any(self.check_backups_in.glob("run-*.json"))
        self._call("videos.update")
        failure = self.fail_updates.get(video_id)
        if isinstance(failure, list):
            if failure:
                raise failure.pop(0)
        elif failure is not None:
            raise failure
        self.updates.append((video_id, dict(snippet)))
        self.set_description(video_id, snippet["description"])

    def set_description(self, video_id: str, description: str) -> None:
        """Change a Video "on YouTube" (as an update, or an edit in Studio, would)."""
        self.videos = [replace(v, description=description) if v.id == video_id else v for v in self.videos]

    def description_of(self, video_id: str) -> str:
        return next(v.description for v in self.videos if v.id == video_id)


class FakeGatewayProvider:
    """Sign-in that succeeds instantly; scriptable for missing secrets, expiry, errors and slow flows."""

    def __init__(self, gateway: FakeGateway, *, has_client_secret: bool = True,
                 connect_error: str | None = None, block_until: threading.Event | None = None) -> None:
        self.gateway = gateway
        self._has_client_secret = has_client_secret
        self._connect_error = connect_error
        self._block_until = block_until
        self.flow_started = threading.Event()
        self.connected = False  # whether a token is "cached"
        self.expired = False
        self.revoked = False

    def has_client_secret(self) -> bool:
        return self._has_client_secret

    def connect(self) -> FakeGateway:
        self.flow_started.set()
        if self._block_until:
            self._block_until.wait(10)
        if self._connect_error:
            raise GatewayError(f"Google sign-in failed: {self._connect_error}")
        self.connected, self.expired, self.revoked = True, False, False
        return self.gateway

    def restore(self) -> FakeGateway | None:
        if self.expired:
            raise AuthExpired("Google sign-in expired")
        return self.gateway if self.connected else None

    def disconnect(self) -> None:
        self.revoked = True
        self.connected = False
        self.expired = False

    def expire(self) -> None:
        """Simulate the cached token becoming unrefreshable."""
        self.expired = True
