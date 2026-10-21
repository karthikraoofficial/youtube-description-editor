"""Proposed changes: what an Operation would do to each Video, with validation Flags."""
from dataclasses import dataclass, field

from app.domain.operations import Operation
from app.domain.transforms import VideoContext, apply
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


def propose(op: Operation, row) -> ProposedChange:
    """Raises OperationError if the Operation can't be applied."""
    before = row["description"]
    after = apply(op, context_of(row))
    changed = after != before
    # Unchanged Videos are never written, so their (pre-existing) text isn't flagged.
    return ProposedChange(video_id=row["id"], title=row["title"], before=before, after=after,
                          changed=changed, after_bytes=byte_length(after), flags=check(after) if changed else [])
