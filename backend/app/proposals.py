"""Proposed changes: what an Operation would do to each Video, with validation Flags."""
from dataclasses import dataclass, field

from app.domain.operations import Operation
from app.domain.transforms import VideoContext, VideoProblem, apply
from app.domain.validation import Flag, byte_length, check


@dataclass(frozen=True)
class ProposedChange:
    video_id: str
    title: str
    before: str
    after: str
    changed: bool
    after_bytes: int
    flags: list[Flag] = field(default_factory=list)


def context_of(row) -> VideoContext:
    return VideoContext(id=row["id"], title=row["title"], description=row["description"],
                        published_at=row["published_at"], duration_s=row["duration_s"])


def _change(row, after: str, flags: list[Flag]) -> ProposedChange:
    before = row["description"]
    return ProposedChange(video_id=row["id"], title=row["title"], before=before, after=after,
                          changed=after != before, after_bytes=byte_length(after), flags=flags)


def propose(op: Operation, row) -> ProposedChange:
    """Raises OperationError if the Operation itself can't be applied (that fails the whole Preview)."""
    try:
        after = apply(op, context_of(row))
    except VideoProblem as e:
        # Only this Video can't take the Operation (ADR-0011): keep it unchanged, but blocked and visible.
        return _change(row, row["description"], [Flag(e.code, f"{e.label}: {e}.", blocking=True)])
    # Validation checks the new text only; an unchanged description isn't written, so it isn't checked.
    return _change(row, after, check(after) if after != row["description"] else [])
