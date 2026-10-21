"""Flags: problems with a proposed description. Blocking Flags stop that Video from being written."""
from dataclasses import dataclass

MAX_DESCRIPTION_BYTES = 5000  # YouTube's limit, counted in UTF-8 bytes


@dataclass(frozen=True)
class Flag:
    code: str
    message: str
    blocking: bool


def byte_length(description: str) -> int:
    return len(description.encode("utf-8"))


def check(description: str) -> list[Flag]:
    flags = []
    size = byte_length(description)
    if size > MAX_DESCRIPTION_BYTES:
        flags.append(Flag("too_long", f"{size:,} bytes: {size - MAX_DESCRIPTION_BYTES:,} over YouTube's "
                                      f"{MAX_DESCRIPTION_BYTES:,}-byte limit.", True))
    if "<" in description or ">" in description:
        flags.append(Flag("angle_brackets", "Contains < or >, which YouTube doesn't allow in descriptions.", True))
    return flags
