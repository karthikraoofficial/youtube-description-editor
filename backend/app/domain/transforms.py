"""The one transform engine (ADR-0001): Preview, review and the written description all come from here.

Pure: no I/O, no clock, no database.
"""
from functools import lru_cache
from typing import NamedTuple

import regex

from app.domain.operations import FindReplace, Operation

REGEX_TIMEOUT_S = 0.25  # per description (ADR-0009); a 20-video Preview stays under ~5 s


class OperationError(ValueError):
    """The Operation can't be applied (e.g. a bad regex). The message is shown to the owner."""


class VideoContext(NamedTuple):
    id: str
    title: str
    description: str
    published_at: str
    duration_s: int


def apply(op: Operation, ctx: VideoContext) -> str:
    match op:
        case FindReplace():
            return _find_replace(op, ctx.description)
    raise OperationError(f"Unsupported operation: {op.type}")  # pragma: no cover


@lru_cache(maxsize=64)
def _compile(pattern: str, flags: int) -> regex.Pattern:
    try:
        return regex.compile(pattern, flags)
    except regex.error as e:
        raise OperationError(f"Invalid regular expression: {e}") from e


_TEMPLATE_ESCAPE = regex.compile(r"\\(?:(\d+)|g<([^>]*)>|.)", regex.DOTALL)


def _check_template(pattern: regex.Pattern, template: str) -> None:
    """Reject group references the pattern can't fill, before any description is touched."""
    for m in _TEMPLATE_ESCAPE.finditer(template):
        number, name = m.group(1), m.group(2)
        if number is not None and int(number) > pattern.groups:
            raise OperationError(f"Invalid replacement: group {number} doesn't exist "
                                 f"(the pattern has {pattern.groups}).")
        known = (name.isdigit() and int(name) <= pattern.groups) or name in pattern.groupindex if name else False
        if name is not None and not known:
            raise OperationError(f"Invalid replacement: group '{name}' doesn't exist.")


def _find_replace(op: FindReplace, text: str) -> str:
    if not op.regex and op.case_sensitive:
        return text.replace(op.find, op.replace)
    flags = regex.MULTILINE | (0 if op.case_sensitive else regex.IGNORECASE)
    pattern = _compile(op.find if op.regex else regex.escape(op.find), flags)
    if op.regex:
        _check_template(pattern, op.replace)
    # Plain mode inserts the replacement literally; regex mode allows \1 and \g<name>.
    repl = op.replace if op.regex else (lambda _m: op.replace)
    try:
        return pattern.sub(repl, text, timeout=REGEX_TIMEOUT_S)
    except TimeoutError as e:
        raise OperationError("The regular expression took too long on a description. Simplify it.") from e
    except (regex.error, IndexError) as e:
        raise OperationError(f"Invalid replacement: {e}") from e
