from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.domain.operations import Operation
from app.domain.transforms import OperationError
from app.domain.validation import MAX_DESCRIPTION_BYTES
from app.proposals import propose

router = APIRouter(prefix="/api")

PREVIEW_SAMPLE_MAX = 20


class PreviewRequest(BaseModel):
    operation: Operation
    video_ids: list[str]


@router.post("/preview")
def preview(body: PreviewRequest, request: Request):
    rows = request.app.state.store.get_videos_by_ids(body.video_ids[:PREVIEW_SAMPLE_MAX])
    try:
        items = [asdict(propose(body.operation, row)) for row in rows]
    except OperationError as e:
        raise HTTPException(422, str(e)) from e
    # Limits come from the backend so the UI never keeps its own copy (ADR-0001).
    return {"items": items, "max_bytes": MAX_DESCRIPTION_BYTES, "sample_max": PREVIEW_SAMPLE_MAX}
