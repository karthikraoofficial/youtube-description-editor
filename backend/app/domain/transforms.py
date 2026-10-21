"""The one transform engine (ADR-0001): Preview, review and the written description all come from here.

Pure: no I/O, no clock, no database.
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import NamedTuple

import regex

from app.domain.operations import Append, FindReplace, Operation, Prepend, Separator, Template

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
        case Append():
            return _append(op, ctx.description)
        case Prepend():
            return _prepend(op, ctx.description)
        case Template():
            return _render(op.template, ctx)
    raise OperationError(f"Unsupported operation: {op.type}")  # pragma: no cover


@lru_cache(maxsize=64)
def _compile(pattern: str, flags: int) -> regex.Pattern:
    try:
        return regex.compile(pattern, flags)
    except regex.error as e:
        raise OperationError(f"Invalid regular expression: {e}") from e


SEPARATORS: dict[Separator, str] = {"blank_line": "\n\n", "newline": "\n", "none": ""}


def _without_blank_edge_lines(text: str) -> str:
    """Drop blank lines at the start and end; keep everything else (including inner spacing) as written."""
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _append(op: Append, description: str) -> str:
    text = _without_blank_edge_lines(op.text)
    sep = SEPARATORS[op.separator]
    base = description.rstrip()
    # "Already there" means exactly what this Operation would have produced: separator + text.
    if op.skip_if_present and (base == text.rstrip() or base.endswith(sep + text.rstrip())):
        return description  # untouched, so it's a no-op that costs no quota
    return base + sep + text if base else text


def _prepend(op: Prepend, description: str) -> str:
    text = _without_blank_edge_lines(op.text)
    sep = SEPARATORS[op.separator]
    base = description.lstrip()
    if op.skip_if_present and (base == text.lstrip() or base.startswith(text.lstrip() + sep)):
        return description
    return text + sep + base if base else text


def _duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


@dataclass(frozen=True)
class TemplateVariable:
    name: str
    help: str
    value: Callable[[VideoContext], str]


_VARIABLES = [
    TemplateVariable("description", "the current description", lambda c: c.description),
    TemplateVariable("title", "the video title", lambda c: c.title),
    TemplateVariable("video_url", "https://www.youtube.com/watch?v=…", lambda c: f"https://www.youtube.com/watch?v={c.id}"),
    TemplateVariable("short_url", "https://youtu.be/…", lambda c: f"https://youtu.be/{c.id}"),
    TemplateVariable("video_id", "the 11-character video id", lambda c: c.id),
    TemplateVariable("publish_date", "publish date, YYYY-MM-DD (UTC)", lambda c: _utc_date(c.published_at)),
    TemplateVariable("duration", "length, e.g. 3:05 or 1:02:03", lambda c: _duration(c.duration_s)),
]
_BY_NAME = {v.name: v for v in _VARIABLES}
# {{ and }} are literal braces; {name} (spaces allowed, one line) is a variable; anything else is a stray brace.
_VARIABLE_TOKEN = regex.compile(r"\{\{|\}\}|\{([^{}\n]*)\}|[{}]")


def _utc_date(iso: str) -> str:
    """The UTC calendar date: deterministic, whatever the computer's time zone."""
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()


def template_variables() -> list[TemplateVariable]:
    return list(_VARIABLES)


def _variable(m: regex.Match) -> TemplateVariable | str:
    """A literal brace (as text) or the variable a token names. Raises OperationError for bad tokens."""
    t = m.group(0)
    if t in ("{{", "}}"):
        return t[0]
    if m.group(1) is None:
        raise OperationError("The template has a single { or }. Write {{ or }} for a literal brace.")
    name = m.group(1).strip()
    if not name:
        raise OperationError("Empty {} in the template. Put a variable name inside, or write {{}} for braces.")
    if name not in _BY_NAME:
        names = ", ".join("{" + v.name + "}" for v in _VARIABLES)
        raise OperationError(f"Unknown variable {{{name}}}. Available: {names}.")
    return _BY_NAME[name]


def variables_used(template: str) -> list[str]:
    """The variable names a template uses, each once, in order. Raises OperationError like rendering."""
    used = [v.name for m in _VARIABLE_TOKEN.finditer(template) if isinstance(v := _variable(m), TemplateVariable)]
    return list(dict.fromkeys(used))


def _render(template: str, ctx: VideoContext) -> str:
    def token(m: regex.Match) -> str:
        v = _variable(m)
        return v if isinstance(v, str) else v.value(ctx)

    # One left-to-right pass, so inserted values are never re-scanned for variables.
    return _VARIABLE_TOKEN.sub(token, template)


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
