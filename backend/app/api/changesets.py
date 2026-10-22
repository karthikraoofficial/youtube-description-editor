from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from app.changesets import UNSET, ChangesetConflict, ChangesetNotFound
from app.domain.operations import Operation
from app.domain.transforms import OperationError

router = APIRouter(prefix="/api/changesets")


class CreateChangeset(BaseModel):
    operation: Operation
    video_ids: list[str] = Field(min_length=1)


class ItemUpdate(BaseModel):
    """Either or both: include/exclude, and a hand edit (`override`; null resets it)."""

    included: bool | None = None
    override: str | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "ItemUpdate":
        # "override": null is meaningful (reset); "included": null is not.
        if self.included is None and "override" not in self.model_fields_set:
            raise ValueError("Send 'included' and/or 'override'")
        return self


def _changesets(request: Request):
    return request.app.state.changesets


@router.post("", status_code=201)
def create(body: CreateChangeset, request: Request):
    try:
        cs_id = _changesets(request).create(body.operation, body.video_ids)
    except OperationError as e:
        raise HTTPException(422, str(e)) from e
    return _changesets(request).get(cs_id)


@router.get("/open")
def open_review(request: Request):
    """The one Changeset still open for review (ADR-0012), so the UI can find it again after a reload."""
    cs_id = _changesets(request).open_id()
    return {"id": cs_id} if cs_id is not None else None


@router.get("/{cs_id}")
def get(cs_id: int, request: Request):
    try:
        return _changesets(request).get(cs_id)
    except ChangesetNotFound as e:
        raise HTTPException(404, "No such review.") from e


@router.patch("/{cs_id}/items/{video_id}")
def update_item(cs_id: int, video_id: str, body: ItemUpdate, request: Request):
    override = body.override if "override" in body.model_fields_set else UNSET
    try:
        return _changesets(request).update_item(cs_id, video_id, included=body.included, override=override)
    except ChangesetNotFound as e:
        raise HTTPException(404, "No such video in this review.") from e
    except ChangesetConflict as e:
        raise HTTPException(409, str(e)) from e
