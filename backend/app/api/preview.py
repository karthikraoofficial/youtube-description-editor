import time
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.domain.operations import Operation, Template
from app.domain.transforms import OperationError, template_variables, variables_used
from app.domain.validation import MAX_DESCRIPTION_BYTES
from app.proposals import ProposedChange, propose

router = APIRouter(prefix="/api")

PREVIEW_SAMPLE_MAX = 20
SUMMARY_BUDGET_S = 10  # a whole-Selection summary gives up rather than tie the server up


class PreviewRequest(BaseModel):
    operation: Operation
    video_ids: list[str]


def _propose_all(request: Request, body: PreviewRequest, ids: list[str],
                 budget_s: float | None = None) -> list[ProposedChange]:
    """Proposed changes for `ids`, in order. Operation problems become a 422 with a readable message."""
    rows = request.app.state.store.get_videos_by_ids(ids)
    deadline = None if budget_s is None else time.monotonic() + budget_s
    changes = []
    try:
        for row in rows:
            if deadline is not None and time.monotonic() >= deadline:
                raise OperationError("Checking every selected video took too long. Simplify the regular "
                                     "expression or select fewer videos.")
            changes.append(propose(body.operation, row))
    except OperationError as e:
        raise HTTPException(422, str(e)) from e
    return changes


@router.post("/preview")
def preview(body: PreviewRequest, request: Request):
    changes = _propose_all(request, body, body.video_ids[:PREVIEW_SAMPLE_MAX])
    op = body.operation
    # Facts about the Operation come from the backend so the UI never re-implements them (ADR-0001).
    keeps = "description" in variables_used(op.template) if isinstance(op, Template) else None
    return {"items": [asdict(c) for c in changes], "max_bytes": MAX_DESCRIPTION_BYTES,
            "sample_max": PREVIEW_SAMPLE_MAX, "keeps_description": keeps}


@router.get("/template-variables")
def list_template_variables():
    return [{"name": v.name, "help": v.help} for v in template_variables()]


@router.post("/preview/summary")
def preview_summary(body: PreviewRequest, request: Request):
    """Counts over the whole Selection, so problems outside the Preview sample are not missed.
    `blocked` and `largest_after_bytes` only consider Videos that would change: the rest aren't written."""
    changes = _propose_all(request, body, body.video_ids, budget_s=SUMMARY_BUDGET_S)
    changed = [c for c in changes if c.changed]
    return {
        "selected": len(changes), "changed": len(changed), "unchanged": len(changes) - len(changed),
        "blocked": sum(1 for c in changed if any(f.blocking for f in c.flags)),
        "largest_after_bytes": max((c.after_bytes for c in changed), default=0),
        "max_bytes": MAX_DESCRIPTION_BYTES,
    }
