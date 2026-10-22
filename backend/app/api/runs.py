import asyncio
import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.runs import ACTIVE, RunConflict, RunNotFound

router = APIRouter(prefix="/api")


class ApplyRequest(BaseModel):
    # The owner confirms the exact number of videos to write; a mismatch writes nothing.
    confirm_count: int


def _runs(request: Request):
    return request.app.state.runs


@router.post("/changesets/{cs_id}/apply", status_code=202)
def apply(cs_id: int, body: ApplyRequest, request: Request):
    try:
        run_id = _runs(request).apply_changeset(cs_id, body.confirm_count)
    except RunNotFound as e:
        raise HTTPException(404, "No such review.") from e
    except RunConflict as e:
        raise HTTPException(409, str(e)) from e
    return {"id": run_id}


@router.get("/runs")
def list_runs(request: Request, unfinished: bool = False):
    return _runs(request).list(unfinished=unfinished)


@router.post("/runs/{run_id}/pause", status_code=202)
def pause(run_id: int, request: Request):
    return _control(request, run_id, "pause")


@router.post("/runs/{run_id}/cancel", status_code=202)
def cancel(run_id: int, request: Request):
    return _control(request, run_id, "cancel")


def _control(request: Request, run_id: int, action: str):
    try:
        _runs(request).request(run_id, action)
    except RunNotFound as e:
        raise HTTPException(404, "No such run.") from e
    except RunConflict as e:
        raise HTTPException(409, str(e)) from e
    return {"id": run_id}


EVENT_INTERVAL_S = 0.5


@router.get("/runs/{run_id}/events")
async def events(run_id: int, request: Request, after_log_id: int = 0):
    """Server-Sent Events while the Run works: its summary, each item's outcome, the log lines after
    `after_log_id` (each sent once, with its id) and today's Quota. Ends when the Run stops."""
    runs = _runs(request)
    ledger = request.app.state.ledger
    try:
        first = await run_in_threadpool(runs.progress, run_id, after_log_id)
    except RunNotFound as e:
        raise HTTPException(404, "No such run.") from e

    async def stream():
        cursor, progress, last = after_log_id, first, None
        while True:
            quota = asdict(await run_in_threadpool(ledger.today))
            if progress["log"]:
                cursor = progress["log"][-1]["id"]
            snapshot = json.dumps({**progress, "log": [], "quota": quota}, sort_keys=True)
            if progress["log"] or snapshot != last:
                last = snapshot
                yield f"data: {json.dumps({**progress, 'quota': quota})}\n\n"
            if progress["run"]["status"] not in ACTIVE or await request.is_disconnected():
                return
            await asyncio.sleep(EVENT_INTERVAL_S)
            progress = await run_in_threadpool(runs.progress, run_id, cursor)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/runs/{run_id}/resume", status_code=202)
def resume(run_id: int, body: ApplyRequest, request: Request):
    try:
        _runs(request).resume(run_id, body.confirm_count)
    except RunNotFound as e:
        raise HTTPException(404, "No such run.") from e
    except RunConflict as e:
        raise HTTPException(409, str(e)) from e
    return {"id": run_id}


@router.get("/runs/{run_id}")
def get_run(run_id: int, request: Request):
    try:
        return _runs(request).get(run_id)
    except RunNotFound as e:
        raise HTTPException(404, "No such run.") from e
