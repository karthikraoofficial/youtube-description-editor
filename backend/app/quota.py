"""The Quota ledger: units spent per Pacific-time day, recorded for every YouTube API request.

YouTube doesn't report remaining quota, so this is an estimate from our own calls.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.store.db import Store
from app.youtube.gateway import Channel, UploadsPage, VideoDetails, YouTubeGateway

DAILY_LIMIT = 10_000
PACIFIC = ZoneInfo("America/Los_Angeles")
COSTS = {
    "channels.list": 1,
    "playlistItems.list": 1,
    "videos.list": 1,
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


class QuotaLedger:
    def __init__(self, store: Store) -> None:
        self._store = store

    def record(self, method: str) -> None:
        self._store.add_quota_event(pacific_date(), method, COSTS[method], None)

    def today(self) -> QuotaToday:
        now = datetime.now(PACIFIC)
        date = pacific_date(now)
        used = self._store.quota_used(date)
        return QuotaToday(date, used, DAILY_LIMIT, max(0, DAILY_LIMIT - used), next_reset(now).isoformat())


class MeteredGateway:
    """Records each request in the ledger before making it: a failed request still costs quota."""

    def __init__(self, inner: YouTubeGateway, ledger: QuotaLedger) -> None:
        self._inner = inner
        self._ledger = ledger

    def get_my_channel(self) -> Channel:
        self._ledger.record("channels.list")
        return self._inner.get_my_channel()

    def list_uploads_page(self, playlist_id: str, page_token: str | None) -> UploadsPage:
        self._ledger.record("playlistItems.list")
        return self._inner.list_uploads_page(playlist_id, page_token)

    def get_videos(self, video_ids: list[str]) -> list[VideoDetails]:
        self._ledger.record("videos.list")
        return self._inner.get_videos(video_ids)
