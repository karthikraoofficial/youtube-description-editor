"""Sync: refresh the local cache with every public Video on the Channel."""
import threading

from app.store.db import Store
from app.youtube.errors import PlaylistNotFound
from app.youtube.gateway import Channel, VideoDetails, YouTubeGateway

BATCH = 50  # videos.list accepts at most 50 ids


class SyncInProgress(Exception):
    pass


class Syncer:
    def __init__(self, store: Store) -> None:
        self._store = store
        self._lock = threading.Lock()

    def sync(self, gateway: YouTubeGateway, channel: Channel) -> int:
        """Returns the number of public Videos now cached. Raises GatewayError / AuthExpired."""
        if not self._lock.acquire(blocking=False):
            raise SyncInProgress()
        try:
            try:
                ids = self._upload_ids(gateway, channel.uploads_playlist_id)
            except PlaylistNotFound:
                # Only believable as "no uploads yet" when nothing is cached; otherwise it is an
                # error, and wiping the cache over it would lose Short labels and edit markers.
                if self._store.video_count():
                    raise
                ids = []
            public: list[VideoDetails] = []
            for i in range(0, len(ids), BATCH):
                public += [v for v in gateway.get_videos(ids[i:i + BATCH]) if v.privacy_status == "public"]
            # Only reached if every request succeeded, so a failed Sync never empties the cache.
            self._store.replace_videos(channel.id, public)
            return len(public)
        finally:
            self._lock.release()

    @staticmethod
    def _upload_ids(gateway: YouTubeGateway, playlist_id: str) -> list[str]:
        ids: list[str] = []
        seen: set[str] = set()
        token: str | None = None
        while True:
            page = gateway.list_uploads_page(playlist_id, token)
            for video_id in page.video_ids:
                if video_id not in seen:
                    seen.add(video_id)
                    ids.append(video_id)
            token = page.next_page_token
            if not token:
                return ids
