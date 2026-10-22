from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.runs import RunConflict, RunNotFound

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
def list_runs(request: Request):
    return _runs(request).list()


@router.get("/runs/{run_id}")
def get_run(run_id: int, request: Request):
    try:
        return _runs(request).get(run_id)
    except RunNotFound as e:
        raise HTTPException(404, "No such run.") from e
