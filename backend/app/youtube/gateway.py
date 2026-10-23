"""The single boundary between the app and YouTube.

A GatewayProvider signs in and hands out a YouTubeGateway. Each gateway method is exactly one
YouTube API request, so its Quota cost is fixed (see app/quota.py). Google implementations live
in `google.py`; in-memory fakes for tests and --fake mode live in `fake.py`.
"""
from dataclasses import dataclass, field
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
class FreshSnippet:
    """A Video's live snippet exactly as YouTube returned it (the Backup), plus its privacy status."""

    id: str
    snippet: dict
    privacy_status: str


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

    def get_snippets(self, video_ids: list[str]) -> list[FreshSnippet]:
        """videos.list (snippet,status) for up to 50 ids: the live snippet, fetched just before writing."""
        ...

    def update_snippet(self, video_id: str, snippet: dict) -> None:
        """videos.update (part=snippet). YouTube replaces the whole snippet with `snippet`."""
        ...


@dataclass(frozen=True)
class SignIn:
    """What Google's callback proved: who signed in, and the credentials to reach their Channel."""
    email: str
    email_verified: bool
    credentials_json: str = field(repr=False)  # holds the refresh token: never print it


class GatewayProvider(Protocol):
    """Google's web sign-in flow, and gateways built from the credentials it returns (ADR-0019). The app
    stores the credentials; the provider never keeps them."""

    def has_client_secret(self) -> bool: ...

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        """Where to send the browser to sign in with Google, asking for identity and YouTube access."""
        ...

    def exchange_code(self, code: str, redirect_uri: str) -> SignIn:
        """Trade the callback's code for credentials and the signed-in email. Raises GatewayError."""
        ...

    def gateway_for(self, credentials_json: str) -> tuple[YouTubeGateway, str | None]:
        """A gateway using stored credentials, and the credentials again if refreshing changed them (else None).
        Raises AuthExpired when they can't be refreshed."""
        ...

    def revoke(self, credentials_json: str) -> None:
        """Withdraw the grant with Google, best effort."""
        ...
