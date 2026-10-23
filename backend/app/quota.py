"""The Quota ledger: units spent per Pacific-time day, recorded for every YouTube API request.

YouTube doesn't report remaining quota, so this is an estimate from our own calls.
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TypeVar
from zoneinfo import ZoneInfo

from app.store.db import Store
from app.youtube.errors import AuthExpired
from app.youtube.gateway import Channel, FreshSnippet, UploadsPage, VideoDetails, YouTubeGateway

T = TypeVar("T")
DAILY_LIMIT = 10_000
UPDATE_UNITS = 50  # one videos.update
PACIFIC = ZoneInfo("America/Los_Angeles")
COSTS = {
    "channels.list": 1,
    "playlistItems.list": 1,
    "videos.list": 1,
    "videos.update": UPDATE_UNITS,
}


def pacific_date(now: datetime | None = None) -> str:
    return (now or datetime.now(PACIFIC)).astimezone(PACIFIC).date().isoformat()


def next_reset(now: datetime | None = None) -> datetime:
    local = (now or datetime.now(PACIFIC)).astimezone(PACIFIC)
    return (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class QuotaToday:
    date_pt: str
    used: int
    limit: int
    remaining: int
    resets_at: str
    update_units: int = UPDATE_UNITS  # what one description update costs, so the UI never hard-codes it


class QuotaLedger:
    def __init__(self, store: Store) -> None:
        self._store = store

    def record(self, method: str) -> None:
        self._store.add_quota_event(pacific_date(), method, COSTS[method], None)

    def mark_exhausted(self) -> None:
        """YouTube said the quota is gone: make today's estimate agree, whatever else used it."""
        remaining = self.today().remaining
        if remaining:
            self._store.add_quota_event(pacific_date(), "quota_exhausted", remaining, None)

    def today(self) -> QuotaToday:
        now = datetime.now(PACIFIC)
        date = pacific_date(now)
        used = self._store.quota_used(date)
        return QuotaToday(date, used, DAILY_LIMIT, max(0, DAILY_LIMIT - used), next_reset(now).isoformat())


class MeteredGateway:
    """Records each request in the ledger before making it: a failed request still costs quota. When Google
    stops accepting the credentials, it calls `on_expired`, so the Connection knows which sign-in expired."""

    def __init__(self, inner: YouTubeGateway, ledger: QuotaLedger,
                 on_expired: Callable[[], None] | None = None) -> None:
        self._inner = inner
        self._ledger = ledger
        self._on_expired = on_expired

    def _send(self, method: str, call: Callable[[], T]) -> T:
        self._ledger.record(method)
        try:
            return call()
        except AuthExpired:
            if self._on_expired:
                self._on_expired()
            raise

    def get_my_channel(self) -> Channel:
        return self._send("channels.list", self._inner.get_my_channel)

    def list_uploads_page(self, playlist_id: str, page_token: str | None) -> UploadsPage:
        return self._send("playlistItems.list", lambda: self._inner.list_uploads_page(playlist_id, page_token))

    def get_videos(self, video_ids: list[str]) -> list[VideoDetails]:
        return self._send("videos.list", lambda: self._inner.get_videos(video_ids))

    def get_snippets(self, video_ids: list[str]) -> list[FreshSnippet]:
        return self._send("videos.list", lambda: self._inner.get_snippets(video_ids))

    def update_snippet(self, video_id: str, snippet: dict) -> None:
        self._send("videos.update", lambda: self._inner.update_snippet(video_id, snippet))
