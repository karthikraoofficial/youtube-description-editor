"""Seam 1: the pure transform engine. Expected values are worked examples, never recomputed."""
import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain.operations import FindReplace, Operation
from app.domain.transforms import OperationError, VideoContext, apply

CTX = VideoContext(id="abc123", title="Late Night Jam", description="", published_at="2025-03-10T18:00:00Z",
                   duration_s=200)


def run(op, description):
    return apply(op, CTX._replace(description=description))


class TestFindReplacePlain:
    def test_replaces_every_occurrence(self):
        op = FindReplace(find="old.link", replace="new.link")
        assert run(op, "a old.link b old.link") == "a new.link b new.link"

    def test_is_case_sensitive_by_default(self):
        assert run(FindReplace(find="Spotify", replace="Apple Music"), "spotify Spotify") == "spotify Apple Music"

    def test_case_insensitive_when_asked(self):
        op = FindReplace(find="spotify", replace="Apple Music", case_sensitive=False)
        assert run(op, "SPOTIFY and Spotify") == "Apple Music and Apple Music"

    def test_special_characters_are_literal(self):
        op = FindReplace(find="a.b (c)", replace="X")
        assert run(op, "axb (c) | a.b (c)") == "axb (c) | X"

    def test_replacement_backslashes_are_literal_in_plain_mode(self):
        assert run(FindReplace(find="x", replace=r"\1\n"), "x") == r"\1\n"

    def test_no_match_returns_the_description_unchanged(self):
        assert run(FindReplace(find="nothing", replace="y"), "Hello\nworld") == "Hello\nworld"

    def test_can_delete_text(self):
        assert run(FindReplace(find=" #ad", replace=""), "Great gear #ad") == "Great gear"

    def test_multiline_find(self):
        op = FindReplace(find="Line 1\nLine 2", replace="One line")
        assert run(op, "Line 1\nLine 2\nLine 3") == "One line\nLine 3"


class TestFindReplaceRegex:
    def test_groups_in_the_replacement(self):
        op = FindReplace(find=r"https?://old\.example/(\w+)", replace=r"https://new.example/\1", regex=True)
        assert run(op, "see http://old.example/abc and https://old.example/xyz") == (
            "see https://new.example/abc and https://new.example/xyz")

    def test_case_toggle_applies_to_regex(self):
        op = FindReplace(find=r"insta\w*", replace="IG", regex=True, case_sensitive=False)
        assert run(op, "Instagram INSTA") == "IG IG"

    def test_anchors_work_per_line(self):
        op = FindReplace(find=r"^- ", replace="• ", regex=True)
        assert run(op, "- one\n- two") == "• one\n• two"

    def test_invalid_regex_is_a_clear_error(self):
        with pytest.raises(OperationError, match="Invalid regular expression"):
            run(FindReplace(find="(unclosed", replace="", regex=True), "x")

    def test_bad_group_reference_is_a_clear_error(self):
        with pytest.raises(OperationError, match="replacement"):
            run(FindReplace(find="a", replace=r"\2", regex=True), "a")

    def test_bad_group_reference_fails_even_when_nothing_matches(self):
        # Otherwise a Preview sample without matches would hide an error that later Videos hit.
        with pytest.raises(OperationError, match="group 2"):
            run(FindReplace(find="(a)", replace=r"\2", regex=True), "no match here")
        with pytest.raises(OperationError, match="group 'nope'"):
            run(FindReplace(find="(?P<x>a)", replace=r"\g<nope>", regex=True), "zzz")

    def test_valid_group_references_pass_the_check(self):
        op = FindReplace(find=r"(?P<word>\w+)@(\w+)", replace=r"\g<word> at \2 (\g<1>)", regex=True)
        assert run(op, "me@site") == "me at site (me)"

    def test_catastrophic_regex_times_out_instead_of_hanging(self):
        with pytest.raises(OperationError, match="too long"):
            run(FindReplace(find=r"(a|aa)+$", replace="", regex=True), "a" * 40 + "b")


class TestOperationParsing:
    def test_find_must_not_be_empty(self):
        with pytest.raises(ValidationError):
            FindReplace(find="", replace="x")

    def test_operations_are_a_tagged_union(self):
        op = TypeAdapter(Operation).validate_python({"type": "find_replace", "find": "a", "replace": "b"})
        assert op == FindReplace(find="a", replace="b")
