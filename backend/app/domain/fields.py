"""Fields: the one part of a Video's Snippet that a Changeset edits (ADR-0022).

Every layer (Preview, Changeset, Override, Stale check, Run, Restore) handles a Field's value as text, so
diffs and hand edits work the same for every Field. Pure: no I/O.
"""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from app.domain import validation
from app.domain.validation import Flag

# The Fields the app can edit; the API refuses any other.
FieldName = Literal["description", "title"]

_LINE_BREAKS = ("blank_line", "newline", "none")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str  # for people, e.g. "Title"
    singular: str  # in sentences, e.g. "each video's title"
    plural: str  # in sentences, e.g. "Writing titles…"
    snippet_key: str  # the key in YouTube's snippet
    cache_column: str  # the column in the cached `videos` table
    check: Callable[[str], list[Flag]]  # validation Flags for a new value
    operations: tuple[str, ...]  # the Operation types this Field accepts, in the order the Edit screen offers them
    separators: tuple[str, ...]  # how Append and Prepend may join text to it; the first is the default
    one_line: bool  # whether a value is a single line (edited in a one-line box)
    size: Callable[[str], int]  # how YouTube measures a value against its limit…
    max_size: int  # …the limit…
    size_unit: str  # …and its unit
    to_snippet: Callable[[str], Any] = lambda text: text  # text -> the snippet's value
    from_snippet: Callable[[Any], str] = lambda value: value or ""  # the snippet's value -> text
    to_cache: Callable[[str], Any] = lambda text: text  # text -> the cache column's value
    from_cache: Callable[[Any], str] = lambda value: value or ""  # the cache column's value -> text


FIELDS: dict[FieldName, FieldSpec] = {
    "description": FieldSpec(
        "description", label="Description", singular="description", plural="descriptions",
        snippet_key="description", cache_column="description", check=validation.check,
        operations=("find_replace", "append", "prepend", "template", "section"), separators=_LINE_BREAKS,
        one_line=False, size=validation.byte_length, max_size=validation.MAX_DESCRIPTION_BYTES, size_unit="bytes"),
    # Template and Section are about multi-line text, so titles take only the one-line Operations (ADR-0022).
    "title": FieldSpec(
        "title", label="Title", singular="title", plural="titles", snippet_key="title", cache_column="title",
        check=validation.check_title, operations=("find_replace", "append", "prepend"),
        separators=("pipe", "dash", "space", "none"), one_line=True, size=len,
        max_size=validation.MAX_TITLE_CHARS, size_unit="characters"),
}


def spec(name: FieldName) -> FieldSpec:
    return FIELDS[name]


def describe(s: FieldSpec) -> dict:
    """What the Edit screen needs to know about a Field, so the UI never keeps its own copy (ADR-0001)."""
    return {"field": s.name, "label": s.label, "singular": s.singular, "plural": s.plural, "one_line": s.one_line,
            "operations": list(s.operations), "separators": list(s.separators), "max_size": s.max_size,
            "size_unit": s.size_unit}


def refusal(name: FieldName, op) -> str | None:
    """Why this Field can't take this Operation, for the owner; None when it can."""
    s = FIELDS[name]
    if op.type not in s.operations:
        return f"{s.plural.capitalize()} can't be edited with this operation."
    separator = getattr(op, "separator", None)
    if separator is not None and separator not in s.separators:
        return f"That separator doesn't work for {s.plural}."
    return None


def value_in_snippet(name: FieldName, snippet: dict) -> str:
    """The Field's text in a Snippet fetched from YouTube (or saved as a Backup). A missing key means empty."""
    s = FIELDS[name]
    return s.from_snippet(snippet.get(s.snippet_key))


def value_in_cache(name: FieldName, row) -> str:
    """The Field's text in a cached Video row."""
    s = FIELDS[name]
    return s.from_cache(row[s.cache_column])
