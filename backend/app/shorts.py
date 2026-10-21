"""Short detection (ADR-0005): probe youtube.com/shorts/<id>, fall back to duration, let the owner override."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, NamedTuple, Protocol

import httpx

SHORT_MAX_S = 180  # YouTube Shorts can be up to 3 minutes
PROBE_WORKERS = 4
PROBE_SPACING_S = 0.1  # minimum gap between probe starts: at most ~10 requests/s
PROBE_TIMEOUT_S = 5
PROBE_BUDGET_S = 120  # after this, remaining Videos use the duration fallback and are re-probed next Sync

ShortSource = Literal["probe", "duration", "manual"]

log = logging.getLogger(__name__)


class ShortLabel(NamedTuple):
    is_short: bool | None  # None = unknown
    source: ShortSource | None


UNKNOWN = ShortLabel(None, None)


class ShortsProber(Protocol):
    def probe(self, video_id: str) -> bool | None:
        """True = Short, False = regular video, None = couldn't tell."""
        ...


class HttpShortsProber:
    """A Short's /shorts/ URL answers 200; any other Video redirects to its /watch page.
    Anything else (consent pages, rate limits, network errors) counts as "couldn't tell"."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(follow_redirects=False, timeout=PROBE_TIMEOUT_S, transport=transport,
                                    headers={"User-Agent": "Mozilla/5.0 (YouTube Description Editor)"})
        self._lock = threading.Lock()
        self._last_start = 0.0

    def probe(self, video_id: str) -> bool | None:
        with self._lock:
            wait = self._last_start + PROBE_SPACING_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_start = time.monotonic()
        try:
            r = self._client.head(f"https://www.youtube.com/shorts/{video_id}")
        except httpx.HTTPError:
            return None
        if r.status_code == 200:
            return True
        if r.is_redirect and "/watch" in r.headers.get("location", ""):
            return False
        return None


class FakeShortsProber:
    """Scripted answers for tests and --fake mode; ids not in `results` get `default`."""

    def __init__(self, results: dict[str, bool | None] | None = None, *, default: bool | None = None) -> None:
        self._results = results or {}
        self._default = default
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def probe(self, video_id: str) -> bool | None:
        with self._lock:
            self.calls.append(video_id)
        return self._results.get(video_id, self._default)


def _fallback(duration_s: int) -> ShortLabel:
    # A zero duration means "unknown", never a guess.
    return ShortLabel(duration_s <= SHORT_MAX_S, "duration") if duration_s > 0 else UNKNOWN


def classify(prober: ShortsProber, videos: list[tuple[str, int]]) -> dict[str, ShortLabel]:
    """(video_id, duration_s) -> ShortLabel. Never raises, and stops probing after PROBE_BUDGET_S."""
    deadline = time.monotonic() + PROBE_BUDGET_S

    def one(item: tuple[str, int]) -> tuple[str, ShortLabel]:
        video_id, duration_s = item
        if time.monotonic() >= deadline:
            return video_id, _fallback(duration_s)
        try:
            verdict = prober.probe(video_id)
        except Exception:  # a probe must never fail the Sync
            log.warning("Short probe crashed for one video; using duration fallback", exc_info=True)
            verdict = None
        return video_id, ShortLabel(verdict, "probe") if verdict is not None else _fallback(duration_s)

    with ThreadPoolExecutor(PROBE_WORKERS) as pool:
        results = dict(pool.map(one, videos))
    fallbacks = sum(1 for label in results.values() if label.source != "probe")
    if fallbacks:
        log.info("Short probe inconclusive for %d of %d videos; used duration fallback", fallbacks, len(videos))
    return results
