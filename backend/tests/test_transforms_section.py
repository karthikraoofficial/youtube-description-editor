"""Seam 1: the section Operation (text between a start and an end marker)."""
import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain.operations import Operation, Section
from app.domain.transforms import BrokenMarkers, VideoContext, apply
from app.proposals import propose

CTX = VideoContext(id="v", title="T", description="", published_at="2025-01-01T00:00:00Z", duration_s=60)
LINKS = "Spotify: https://sp.example\nInstagram: @me"


def section(**kw):
    return Section(start_marker="[LINKS]", end_marker="[/LINKS]", content=LINKS, **kw)


def run(op, description):
    return apply(op, CTX._replace(description=description))


class TestReplace:
    def test_replaces_everything_between_the_markers_and_keeps_them(self):
        before = "Intro\n\n[LINKS]\nold stuff\nmore old\n[/LINKS]\n\nOutro"
        assert run(section(), before) == f"Intro\n\n[LINKS]\n{LINKS}\n[/LINKS]\n\nOutro"

    def test_markers_on_one_line_work_too(self):
        assert run(section(), "a [LINKS]x[/LINKS] b") == f"a [LINKS]\n{LINKS}\n[/LINKS] b"

    def test_empty_content_empties_the_section(self):
        assert run(section().model_copy(update={"content": ""}), "[LINKS]\nold\n[/LINKS]") == "[LINKS]\n[/LINKS]"

    def test_already_up_to_date_is_a_no_op(self):
        current = f"Intro\n\n[LINKS]\n{LINKS}\n[/LINKS]"
        assert run(section(), current) == current

    def test_blank_lines_around_the_content_are_dropped(self):
        op = section().model_copy(update={"content": f"\n\n{LINKS}\n\n"})
        assert run(op, "[LINKS]\nold\n[/LINKS]") == f"[LINKS]\n{LINKS}\n[/LINKS]"


class TestMissingMarkers:
    def test_append_adds_a_new_section_after_a_blank_line(self):
        assert run(section(if_missing="append"), "Intro\n\n") == f"Intro\n\n[LINKS]\n{LINKS}\n[/LINKS]"

    def test_prepend_adds_it_at_the_top(self):
        assert run(section(if_missing="prepend"), "Intro") == f"[LINKS]\n{LINKS}\n[/LINKS]\n\nIntro"

    def test_skip_leaves_the_video_alone(self):
        assert run(section(if_missing="skip"), "Intro") == "Intro"

    def test_append_is_the_default_and_an_empty_description_gets_just_the_section(self):
        assert run(section(), "") == f"[LINKS]\n{LINKS}\n[/LINKS]"


class TestBrokenMarkers:
    @pytest.mark.parametrize("description,reason", [
        ("[LINKS]\nno end", "no [/LINKS] after [LINKS]"),
        ("[/LINKS] then [LINKS]", "no [/LINKS] after [LINKS]"),
        ("only an end [/LINKS]", "[/LINKS] without [LINKS]"),
        ("[LINKS]a[/LINKS] and [LINKS]b[/LINKS]", "[LINKS] appears 2 times"),
        ("[LINKS]a[/LINKS][/LINKS]", "[/LINKS] appears 2 times"),
    ])
    def test_are_reported_not_guessed(self, description, reason):
        with pytest.raises(BrokenMarkers, match=__import__("re").escape(reason)):
            run(section(), description)

    def test_a_broken_video_is_blocked_in_its_proposed_change_instead_of_failing_the_preview(self):
        row = {"id": "v", "title": "T", "description": "[LINKS] no end", "published_at": CTX.published_at,
               "duration_s": 60}
        p = propose(section(), row)
        assert p.changed is False
        assert p.after == "[LINKS] no end"
        assert [(f.code, f.blocking) for f in p.flags] == [("markers_broken", True)]
        assert "no [/LINKS] after [LINKS]" in p.flags[0].message


class TestValidation:
    @pytest.mark.parametrize("start,end", [("", "[/X]"), ("[X]", ""), ("[X]", "[X]"), ("<!-- a -->", "[/X]"),
                                           ("[X]\n", "[/X]"), ("  ", "[/X]")])
    def test_bad_markers_are_rejected(self, start, end):
        with pytest.raises(ValidationError):
            Section(start_marker=start, end_marker=end, content="x")

    def test_content_containing_a_marker_is_rejected_so_reruns_stay_safe(self):
        with pytest.raises(ValidationError, match="content"):
            Section(start_marker="[A]", end_marker="[/A]", content="see [/A] here")

    def test_unknown_if_missing_is_rejected(self):
        with pytest.raises(ValidationError):
            Section(start_marker="[A]", end_marker="[/A]", content="x", if_missing="ignore")

    def test_section_joins_the_union(self):
        data = {"type": "section", "start_marker": "[A]", "end_marker": "[/A]", "content": "x"}
        assert TypeAdapter(Operation).validate_python(data) == Section(start_marker="[A]", end_marker="[/A]",
                                                                       content="x")
