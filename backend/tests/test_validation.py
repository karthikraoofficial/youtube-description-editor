"""Seam 1: description validation (YouTube's limits)."""
from app.domain.validation import check


def codes(description):
    return [(f.code, f.blocking) for f in check(description)]


def test_a_normal_description_has_no_flags():
    assert codes("Hello\nworld") == []


def test_exactly_5000_bytes_is_allowed():
    assert codes("a" * 5000) == []


def test_over_5000_bytes_is_blocking():
    assert codes("a" * 5001) == [("too_long", True)]


def test_length_counts_utf8_bytes_not_characters():
    # 1,250 emoji = 5,000 bytes (4 each): allowed. One more character tips it over.
    assert codes("🎸" * 1250) == []
    assert codes("🎸" * 1250 + "a") == [("too_long", True)]
    # 2,500 "é" = 5,000 bytes (2 each)
    assert codes("é" * 2501) == [("too_long", True)]


def test_angle_brackets_are_blocking():
    assert codes("a <b> c") == [("angle_brackets", True)]
    assert codes("5 > 3") == [("angle_brackets", True)]


def test_flag_messages_are_specific():
    [flag] = check("a" * 5010)
    assert flag.message == "5,010 bytes: 10 over YouTube's 5,000-byte limit."
    [flag] = check("x <y")
    assert flag.message == "Contains < or >, which YouTube doesn't allow in descriptions."


def test_both_problems_are_reported():
    assert codes("<" * 5001) == [("too_long", True), ("angle_brackets", True)]
