from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.changesets import ChangesetConflict, ChangesetNotFound
from app.domain.operations import Operation
from app.domain.transforms import OperationError

router = APIRouter(prefix="/api/changesets")


class CreateChangeset(BaseModel):
    operation: Operation
    video_ids: list[str] = Field(min_length=1)


class ItemUpdate(BaseModel):
    included: bool


def _changesets(request: Request):
    return request.app.state.changesets


@router.post("", status_code=201)
def create(body: CreateChangeset, request: Request):
    try:
        cs_id = _changesets(request).create(body.operation, body.video_ids)
    except OperationError as e:
        raise HTTPException(422, str(e)) from e
    return _changesets(request).get(cs_id)


@router.get("/{cs_id}")
def get(cs_id: int, request: Request):
    try:
        return _changesets(request).get(cs_id)
    except ChangesetNotFound as e:
        raise HTTPException(404, "No such review.") from e


@router.patch("/{cs_id}/items/{video_id}")
def update_item(cs_id: int, video_id: str, body: ItemUpdate, request: Request):
    try:
        return _changesets(request).set_included(cs_id, video_id, body.included)
    except ChangesetNotFound as e:
        raise HTTPException(404, "No such video in this review.") from e
    except ChangesetConflict as e:
        raise HTTPException(409, str(e)) from e
