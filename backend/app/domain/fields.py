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
FieldName = Literal["description"]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    plural: str  # for messages, e.g. "Writing descriptions…"
    snippet_key: str  # the key in YouTube's snippet
    cache_column: str  # the column in the cached `videos` table
    check: Callable[[str], list[Flag]]  # validation Flags for a new value
    to_snippet: Callable[[str], Any] = lambda text: text  # text -> the snippet's value
    from_snippet: Callable[[Any], str] = lambda value: value or ""  # the snippet's value -> text
    to_cache: Callable[[str], Any] = lambda text: text  # text -> the cache column's value
    from_cache: Callable[[Any], str] = lambda value: value or ""  # the cache column's value -> text


FIELDS: dict[FieldName, FieldSpec] = {
    "description": FieldSpec("description", plural="descriptions", snippet_key="description",
                             cache_column="description", check=validation.check),
}


def spec(name: FieldName) -> FieldSpec:
    return FIELDS[name]


def value_in_snippet(name: FieldName, snippet: dict) -> str:
    """The Field's text in a Snippet fetched from YouTube (or saved as a Backup). A missing key means empty."""
    s = FIELDS[name]
    return s.from_snippet(snippet.get(s.snippet_key))


def value_in_cache(name: FieldName, row) -> str:
    """The Field's text in a cached Video row."""
    s = FIELDS[name]
    return s.from_cache(row[s.cache_column])
