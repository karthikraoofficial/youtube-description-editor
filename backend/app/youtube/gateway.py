"""The single boundary between the app and YouTube.

A GatewayProvider signs in and hands out a YouTubeGateway. Each gateway method is exactly one
YouTube API request, so its Quota cost is fixed (see app/quota.py). Google implementations live
in `google.py`; in-memory fakes for tests and --fake mode live in `fake.py`.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Channel:
    id: str
    title: str
    avatar_url: str | None
    uploads_playlist_id: str


@dataclass(frozen=True)
class VideoDetails:
    id: str
    title: str
    description: str
    category_id: str
    tags: tuple[str, ...]
    default_language: str | None
    default_audio_language: str | None
    published_at: str
    duration_s: int
    privacy_status: str
    thumbnail_url: str | None


@dataclass(frozen=True)
class UploadsPage:
    video_ids: list[str]
    next_page_token: str | None


class YouTubeGateway(Protocol):
    def get_my_channel(self) -> Channel:
        """channels.list (mine)."""
        ...

    def list_uploads_page(self, playlist_id: str, page_token: str | None) -> UploadsPage:
        """One playlistItems.list page (up to 50) of the uploads playlist."""
        ...

    def get_videos(self, video_ids: list[str]) -> list[VideoDetails]:
        """videos.list for up to 50 ids; unknown ids are simply absent."""
        ...


class GatewayProvider(Protocol):
    def has_client_secret(self) -> bool: ...

    def connect(self) -> YouTubeGateway:
        """Run the Google consent flow and cache the token. Raises GatewayError."""
        ...

    def restore(self) -> YouTubeGateway | None:
        """Use the cached token, if any. Raises AuthExpired when it can't be refreshed."""
        ...

    def disconnect(self) -> None:
        """Revoke the token (best effort) and delete it."""
        ...
