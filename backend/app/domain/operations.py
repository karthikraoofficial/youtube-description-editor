"""Operations: the rules that turn a Video's description into a new one (see CONTEXT.md)."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.validation import has_angle_brackets


class _Op(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FindReplace(_Op):
    type: Literal["find_replace"] = "find_replace"
    find: str = Field(min_length=1)
    replace: str = ""
    regex: bool = False
    case_sensitive: bool = True


# Line breaks join description text; titles are one line, so they join with a space, " | " or " - ".
Separator = Literal["blank_line", "newline", "none", "space", "pipe", "dash"]


def _not_blank(v: str) -> str:
    if not v.strip():
        raise ValueError("This can't be empty")
    return v


class _AddText(_Op):
    text: str
    separator: Separator = "blank_line"
    skip_if_present: bool = True  # re-running never adds the text twice

    _text_not_blank = field_validator("text")(_not_blank)


class Append(_AddText):
    """Append to Description: add text after the existing description."""

    type: Literal["append"] = "append"


class Prepend(_AddText):
    type: Literal["prepend"] = "prepend"


class Template(_Op):
    """Replace the whole description with a template filled in per Video ({description} keeps the old text)."""

    type: Literal["template"] = "template"
    template: str

    _template_not_blank = field_validator("template")(_not_blank)


def _marker(v: str) -> str:
    if not v.strip():
        raise ValueError("A marker can't be empty")
    if "\n" in v:
        raise ValueError("A marker must be on one line")
    if has_angle_brackets(v):
        raise ValueError("YouTube doesn't allow < or > in descriptions, so markers can't use them")
    return v


class Section(_Op):
    """Replace the text between a start and an end marker, or add the section where it's missing."""

    type: Literal["section"] = "section"
    start_marker: str
    end_marker: str
    content: str = ""
    if_missing: Literal["append", "prepend", "skip"] = "append"

    _markers_valid = field_validator("start_marker", "end_marker")(_marker)

    @model_validator(mode="after")
    def _unambiguous(self) -> "Section":
        # If one marker contained the other, counting and finding them would be ambiguous.
        if self.start_marker in self.end_marker or self.end_marker in self.start_marker:
            raise ValueError("The start and end markers must differ, and neither may contain the other")
        # A marker inside the content would break the section the next time it's run.
        if self.start_marker in self.content or self.end_marker in self.content:
            raise ValueError("The content can't contain the start or end marker")
        return self


# A tagged union: each Operation is told apart by its "type".
Operation = Annotated[FindReplace | Append | Prepend | Template | Section, Field(discriminator="type")]


SUMMARY_TEXT_MAX = 40


def _short(text: str) -> str:
    """The first line, shortened for a one-line summary."""
    first, _, rest = text.strip("\n").partition("\n")
    if len(first) > SUMMARY_TEXT_MAX:
        return first[:SUMMARY_TEXT_MAX] + "…"
    return f"{first} …" if rest.strip() else first


def summarize(op: Operation, field=None) -> str:
    """A one-line description of an Operation, for History. `field` is the Field's registry entry (ADR-0022);
    other Fields than the description say which Field they changed."""
    elsewhere = field is not None and field.name != "description"
    match op:
        case FindReplace():
            kind = "regex " if op.regex else ""
            where = f" in {field.plural}" if elsewhere else ""
            return f'Replace {kind}"{_short(op.find)}" with "{_short(op.replace)}"{where}'
        case Append():
            return f'Append to {field.label if elsewhere else "Description"}: "{_short(op.text)}"'
        case Prepend():
            where = f" to {field.label}" if elsewhere else ""
            return f'Prepend{where}: "{_short(op.text)}"'
        case Template():
            return f'Template: "{_short(op.template)}"'
        case Section():
            return f"Section between {op.start_marker} and {op.end_marker}"
    raise TypeError(f"Unknown operation {op!r}")  # pragma: no cover
