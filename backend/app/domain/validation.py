"""Flags: problems with a proposed value of a Field. Blocking Flags stop that Video from being written."""
from dataclasses import dataclass

MAX_DESCRIPTION_BYTES = 5000  # YouTube's limit, counted in UTF-8 bytes
MAX_TITLE_CHARS = 100  # YouTube's limit, counted in characters


@dataclass(frozen=True)
class Flag:
    code: str
    message: str
    blocking: bool


def byte_length(description: str) -> int:
    return len(description.encode("utf-8"))


def is_blocked(flags) -> bool:
    """Any blocking Flag stops the Video from being written. Accepts Flags or their dict form."""
    return any(f.blocking if isinstance(f, Flag) else f["blocking"] for f in flags)


def has_angle_brackets(text: str) -> bool:
    return "<" in text or ">" in text


def check(description: str) -> list[Flag]:
    flags = []
    size = byte_length(description)
    if size > MAX_DESCRIPTION_BYTES:
        flags.append(Flag("too_long", f"{size:,} bytes: {size - MAX_DESCRIPTION_BYTES:,} over YouTube's "
                                      f"{MAX_DESCRIPTION_BYTES:,}-byte limit.", True))
    if has_angle_brackets(description):
        flags.append(Flag("angle_brackets", "Contains < or >, which YouTube doesn't allow in descriptions.", True))
    return flags


def check_title(title: str) -> list[Flag]:
    flags = []
    if not title.strip():
        flags.append(Flag("empty", "YouTube needs a title; this one would be empty.", True))
    if len(title) > MAX_TITLE_CHARS:
        flags.append(Flag("too_long", f"{len(title)} characters: {len(title) - MAX_TITLE_CHARS} over YouTube's "
                                      f"{MAX_TITLE_CHARS}-character limit for titles.", True))
    if has_angle_brackets(title):
        flags.append(Flag("angle_brackets", "Contains < or >, which YouTube doesn't allow in titles.", True))
    if "\n" in title or "\r" in title:
        flags.append(Flag("line_break", "A title must be on one line.", True))
    return flags
