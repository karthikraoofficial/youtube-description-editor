"""The single boundary between the app and YouTube.

A GatewayProvider signs in and hands out a YouTubeGateway. Google implementations live in
`google.py`; in-memory fakes for tests and --fake mode live in `fake.py`.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Channel:
    id: str
    title: str
    avatar_url: str | None
    uploads_playlist_id: str


class YouTubeGateway(Protocol):
    def get_my_channel(self) -> Channel: ...


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
