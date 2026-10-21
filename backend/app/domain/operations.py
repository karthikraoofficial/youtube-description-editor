"""Operations: the rules that turn a Video's description into a new one (see CONTEXT.md)."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Op(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FindReplace(_Op):
    type: Literal["find_replace"] = "find_replace"
    find: str = Field(min_length=1)
    replace: str = ""
    regex: bool = False
    case_sensitive: bool = True


# A tagged union: later Operations join it as new members.
Operation = Annotated[FindReplace, Field(discriminator="type")]
