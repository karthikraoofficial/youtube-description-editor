"""Operations: the rules that turn a Video's description into a new one (see CONTEXT.md)."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Op(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FindReplace(_Op):
    type: Literal["find_replace"] = "find_replace"
    find: str = Field(min_length=1)
    replace: str = ""
    regex: bool = False
    case_sensitive: bool = True


Separator = Literal["blank_line", "newline", "none"]


class _AddText(_Op):
    text: str
    separator: Separator = "blank_line"
    skip_if_present: bool = True  # re-running never adds the text twice

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Enter the text to add")
        return v


class Append(_AddText):
    """Append to Description: add text after the existing description."""

    type: Literal["append"] = "append"


class Prepend(_AddText):
    type: Literal["prepend"] = "prepend"


# A tagged union: each Operation is told apart by its "type".
Operation = Annotated[FindReplace | Append | Prepend, Field(discriminator="type")]
