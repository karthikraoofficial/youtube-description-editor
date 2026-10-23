"""Flags: problems with a proposed value of a Field. Blocking Flags stop that Video from being written."""
from dataclasses import dataclass

MAX_DESCRIPTION_BYTES = 5000  # YouTube's limit, counted in UTF-8 bytes
MAX_TITLE_CHARS = 100  # YouTube's limit, counted in characters
MAX_TAGS_CHARS = 500  # YouTube's limit for all of a Video's tags together (see tags_size)


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


def tags_size(tags_text: str) -> int:
    """How YouTube counts tags against their limit: each tag's characters, 2 more for the quotes around a tag
    that contains a space, and 1 for each comma between tags. `tags_text` holds one tag per line, as written
    (a tidied list has no padding, so nothing is trimmed here)."""
    tags = [t for t in tags_text.split("\n") if t]
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1)


def check_tags(tags_text: str) -> list[Flag]:
    flags = []
    size = tags_size(tags_text)
    if size > MAX_TAGS_CHARS:
        flags.append(Flag("too_long", f"{size:,} characters as YouTube counts them: {size - MAX_TAGS_CHARS:,} over "
                                      f"its {MAX_TAGS_CHARS}-character limit for tags.", True))
    if has_angle_brackets(tags_text):
        flags.append(Flag("angle_brackets", "Contains < or >, which YouTube doesn't allow in tags.", True))
    if "," in tags_text:
        flags.append(Flag("comma", "A tag contains a comma, which YouTube reads as two tags.", True))
    return flags
