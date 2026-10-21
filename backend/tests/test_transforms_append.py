"""Seam 1: Append to Description and Prepend."""
import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain.operations import Append, Operation, Prepend
from app.domain.transforms import VideoContext, apply

CTX = VideoContext(id="abc123", title="T", description="", published_at="2025-01-01T00:00:00Z", duration_s=60)
FOOTER = "Lessons: https://example.com/lessons"


def run(op, description):
    return apply(op, CTX._replace(description=description))


class TestAppend:
    def test_blank_line_separator_by_default(self):
        assert run(Append(text=FOOTER), "My song.") == f"My song.\n\n{FOOTER}"

    def test_newline_separator(self):
        assert run(Append(text=FOOTER, separator="newline"), "My song.") == f"My song.\n{FOOTER}"

    def test_no_separator(self):
        assert run(Append(text=" #guitar", separator="none"), "My song.") == "My song. #guitar"

    def test_trailing_whitespace_on_the_existing_description_is_trimmed_first(self):
        assert run(Append(text=FOOTER), "My song.\n\n\n  \n") == f"My song.\n\n{FOOTER}"

    def test_an_empty_description_gets_no_leading_separator(self):
        assert run(Append(text=FOOTER), "") == FOOTER
        assert run(Append(text=FOOTER), "  \n ") == FOOTER

    def test_leading_and_trailing_blank_lines_in_the_text_are_dropped(self):
        assert run(Append(text="\n\nLine A\nLine B\n\n"), "Desc") == "Desc\n\nLine A\nLine B"

    def test_multi_line_text_is_kept_as_written(self):
        text = "Gear:\n- Guitar: Cort KX507\n- Amp: none"
        assert run(Append(text=text), "Desc") == f"Desc\n\n{text}"

    def test_skip_if_present_leaves_descriptions_that_already_end_with_the_text(self):
        op = Append(text=FOOTER, skip_if_present=True)
        already = f"My song.\n\n{FOOTER}\n"
        assert run(op, already) == already  # untouched, not even trimmed: a no-op costs no quota

    def test_skip_if_present_is_idempotent(self):
        op = Append(text=FOOTER, skip_if_present=True)
        once = run(op, "My song.")
        assert run(op, once) == once

    def test_without_skip_the_text_is_appended_again(self):
        once = f"My song.\n\n{FOOTER}"
        assert run(Append(text=FOOTER, skip_if_present=False), once) == f"{once}\n\n{FOOTER}"

    def test_skip_is_on_by_default(self):
        once = f"My song.\n\n{FOOTER}"
        assert run(Append(text=FOOTER), once) == once

    def test_skip_needs_the_separator_too_not_just_a_matching_ending(self):
        # "…see Footer" merely ends with the same words; this Operation didn't add them.
        assert run(Append(text="Footer"), "Please see Footer") == "Please see Footer\n\nFooter"
        assert run(Append(text="Footer", separator="newline"), "Intro\nFooter") == "Intro\nFooter"

    def test_skip_matches_a_description_that_is_only_the_text(self):
        assert run(Append(text=FOOTER), FOOTER) == FOOTER


class TestPrepend:
    def test_blank_line_separator_by_default(self):
        assert run(Prepend(text="NEW ALBUM OUT NOW"), "My song.") == "NEW ALBUM OUT NOW\n\nMy song."

    def test_leading_whitespace_is_trimmed_and_empty_gets_no_separator(self):
        assert run(Prepend(text="Hi", separator="newline"), "\n\n  My song.") == "Hi\nMy song."
        assert run(Prepend(text="Hi"), "") == "Hi"

    def test_skip_if_present_checks_the_start(self):
        op = Prepend(text="NEW ALBUM", skip_if_present=True)
        assert run(op, "NEW ALBUM\n\nMy song.") == "NEW ALBUM\n\nMy song."
        assert run(op, "NEW ALBUMS are coming") == "NEW ALBUM\n\nNEW ALBUMS are coming"


class TestParsing:
    def test_text_must_contain_something(self):
        with pytest.raises(ValidationError):
            Append(text="  \n ")

    def test_unknown_separator_is_rejected(self):
        with pytest.raises(ValidationError):
            Append(text="x", separator="comma")

    def test_append_and_prepend_join_the_union(self):
        adapter = TypeAdapter(Operation)
        assert adapter.validate_python({"type": "append", "text": "x"}) == Append(text="x")
        assert adapter.validate_python({"type": "prepend", "text": "x"}) == Prepend(text="x")
