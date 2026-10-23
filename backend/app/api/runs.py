from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.runs import RunConflict, RunInvalid, RunNotFound

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


class StepRequest(BaseModel):
    # A random id per browser tab: the tab holding a Run's lease is the only one that may write it (ADR-0017).
    driver: str = Field(min_length=8, max_length=64)


def _progress(request: Request, run_id: int, after_log_id: int) -> dict:
    """The live view: the summary, each item's outcome (no descriptions), the log lines after `after_log_id`
    and today's Quota."""
    try:
        progress = _runs(request).progress(run_id, after_log_id)
    except RunNotFound as e:
        raise HTTPException(404, "No such run.") from e
    return {**progress, "quota": asdict(request.app.state.ledger.today())}


@router.post("/runs/{run_id}/step")
def step(run_id: int, body: StepRequest, request: Request, after_log_id: int = 0):
    """Write the Run's next Videos for up to about 40 s, then report progress. The Run screen calls this
    until the Run stops."""
    try:
        _runs(request).step(run_id, body.driver)
    except RunNotFound as e:
        raise HTTPException(404, "No such run.") from e
    except RunConflict as e:
        raise HTTPException(409, str(e)) from e
    return _progress(request, run_id, after_log_id)


@router.get("/runs/{run_id}/progress")
def progress(run_id: int, request: Request, after_log_id: int = 0):
    """For a tab that is watching a Run another tab drives."""
    return _progress(request, run_id, after_log_id)


class RestoreRequest(BaseModel):
    # The owner confirms how many videos will be restored; a mismatch writes nothing.
    confirm_count: int
    video_ids: list[str] | None = None  # omit to restore every video the run wrote


@router.post("/runs/{run_id}/restore", status_code=202)
def restore(run_id: int, body: RestoreRequest, request: Request):
    try:
        new_id = _runs(request).restore(run_id, body.confirm_count, body.video_ids)
    except RunNotFound as e:
        raise HTTPException(404, "No such run.") from e
    except RunInvalid as e:
        raise HTTPException(422, str(e)) from e
    except RunConflict as e:
        raise HTTPException(409, str(e)) from e
    return {"id": new_id}


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
