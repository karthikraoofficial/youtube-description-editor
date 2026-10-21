from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.errors import CONNECT_FIRST, SIGN_IN_EXPIRED, youtube_errors
from app.store.db import LAST_SYNC_AT
from app.sync import SyncInProgress

router = APIRouter(prefix="/api")


def _video(row) -> dict:
    return {
        "id": row["id"], "title": row["title"], "description": row["description"],
        "published_at": row["published_at"], "duration_s": row["duration_s"],
        "thumbnail_url": row["thumbnail_url"],
        "is_short": None if row["is_short"] is None else bool(row["is_short"]),
        "short_source": row["short_source"], "edited": row["last_edited_run_id"] is not None,
    }


def _sync_status(store) -> dict:
    return {"last_sync_at": store.get_setting(LAST_SYNC_AT), "video_count": store.video_count()}


@router.post("/sync")
def sync(request: Request):
    state = request.app.state
    with youtube_errors(state.connection):
        status = state.connection.status()
        if status.state == "expired":
            raise HTTPException(401, SIGN_IN_EXPIRED)
        if status.state != "connected":
            raise HTTPException(409, CONNECT_FIRST)
        try:
            state.syncer.sync(state.connection.gateway(), status.channel)
        except SyncInProgress as e:
            raise HTTPException(409, "A sync is already running.") from e
    return _sync_status(state.store)


@router.get("/sync/status")
def sync_status(request: Request):
    return _sync_status(request.app.state.store)


@router.get("/videos")
def list_videos(request: Request):
    return [_video(r) for r in request.app.state.store.list_videos()]


class ShortOverride(BaseModel):
    is_short: bool


@router.patch("/videos/{video_id}")
def override_short(video_id: str, body: ShortOverride, request: Request):
    store = request.app.state.store
    row = store.get_video(video_id) if store.set_short_manually(video_id, body.is_short) else None
    if row is None:  # also covers a Sync dropping the Video in between
        raise HTTPException(404, "No such video in the cache.")
    return _video(row)


@router.get("/quota")
def quota(request: Request):
    return asdict(request.app.state.ledger.today())
