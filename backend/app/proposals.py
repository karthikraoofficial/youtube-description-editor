"""Proposed changes: what an Operation would do to one Field of each Video, with validation Flags."""
from dataclasses import dataclass, field

from app.domain import fields
from app.domain.fields import FieldName
from app.domain.operations import Operation
from app.domain.transforms import VideoContext, VideoProblem, apply_to
from app.domain.validation import Flag


@dataclass(frozen=True)
class ProposedChange:
    video_id: str
    title: str
    before: str
    after: str
    changed: bool
    after_size: int  # measured as YouTube measures this Field (bytes, characters)
    flags: list[Flag] = field(default_factory=list)


def context_of(row) -> VideoContext:
    return VideoContext(id=row["id"], title=row["title"], description=row["description"],
                        published_at=row["published_at"], duration_s=row["duration_s"])


def _change(row, field: FieldName, before: str, after: str, flags: list[Flag]) -> ProposedChange:
    return ProposedChange(video_id=row["id"], title=row["title"], before=before, after=after,
                          changed=after != before, after_size=fields.spec(field).size(after), flags=flags)


def propose(op: Operation, row, field: FieldName = "description") -> ProposedChange:
    """Raises OperationError if the Operation itself can't be applied (that fails the whole Preview)."""
    before = fields.value_in_cache(field, row)
    try:
        after = apply_to(op, before, context_of(row))
    except VideoProblem as e:
        # Only this Video can't take the Operation (ADR-0011): keep it unchanged, but blocked and visible.
        return _change(row, field, before, before, [Flag(e.code, f"{e.label}: {e}.", blocking=True)])
    # Validation checks the new text only; an unchanged value isn't written, so it isn't checked.
    return _change(row, field, before, after, fields.spec(field).check(after) if after != before else [])
