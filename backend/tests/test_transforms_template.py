"""Seam 1: the template Operation."""
import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain.operations import Operation, Template
from app.domain.transforms import OperationError, VideoContext, apply, template_variables, variables_used

CTX = VideoContext(id="dQw4w9WgXcQ", title="Late Night Jam", description="Old text.",
                   published_at="2025-03-10T18:30:00Z", duration_s=3723)


def run(template, ctx=CTX):
    return apply(Template(template=template), ctx)


def test_every_variable():
    assert run("{title}|{video_id}|{video_url}|{short_url}|{publish_date}|{duration}|{description}") == (
        "Late Night Jam|dQw4w9WgXcQ|https://www.youtube.com/watch?v=dQw4w9WgXcQ|https://youtu.be/dQw4w9WgXcQ"
        "|2025-03-10|1:02:03|Old text.")


def test_short_durations_use_minutes_and_seconds():
    assert run("{duration}", CTX._replace(duration_s=45)) == "0:45"
    assert run("{duration}", CTX._replace(duration_s=185)) == "3:05"


def test_a_typical_footer_keeps_the_existing_description():
    assert run("{description}\n\nWatch in full: {video_url}") == (
        "Old text.\n\nWatch in full: https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_variables_can_repeat_and_text_is_kept_verbatim():
    assert run("{title} — {title}\n  indented\n") == "Late Night Jam — Late Night Jam\n  indented\n"


def test_doubled_braces_are_literal_braces():
    assert run("{{title}} is {title}") == "{title} is Late Night Jam"
    assert run("a {{ b }} c") == "a { b } c"


def test_values_are_inserted_literally_even_if_they_contain_braces():
    assert run("{title}", CTX._replace(title="{video_id} {{x}}")) == "{video_id} {{x}}"


def test_unknown_variable_is_an_error_naming_it():
    with pytest.raises(OperationError, match=r"Unknown variable \{titel\}"):
        run("{titel}")


def test_lone_braces_are_an_error():
    with pytest.raises(OperationError, match="single { or }"):
        run("Price: {")
    with pytest.raises(OperationError, match="single { or }"):
        run("smile :}")


def test_template_must_not_be_blank():
    with pytest.raises(ValidationError):
        Template(template="   ")


def test_template_joins_the_union():
    assert TypeAdapter(Operation).validate_python({"type": "template", "template": "{title}"}) == Template(
        template="{title}")


def test_spaces_inside_braces_are_allowed():
    assert run("{ title }") == "Late Night Jam"


def test_empty_braces_and_multi_line_names_get_clear_errors():
    with pytest.raises(OperationError, match=r"Empty \{\}"):
        run("Hi {}")
    with pytest.raises(OperationError, match="single { or }"):
        run("{title\n}")


def test_unknown_variable_message_uses_the_trimmed_name():
    with pytest.raises(OperationError, match=r"Unknown variable \{nope\}\."):
        run("{ nope }")


@pytest.mark.parametrize("template,keeps", [
    ("{description}\n\nfooter", True),
    ("{ description } and more", True),
    ("{{description}} is literal", False),
    ("{title} only", False),
])
def test_variables_used_tells_whether_the_old_text_is_kept(template, keeps):
    assert ("description" in variables_used(template)) is keeps


def test_variables_used_lists_each_once_in_order():
    assert variables_used("{title} {video_url} {title}") == ["title", "video_url"]


def test_the_variable_list_is_published_for_the_ui():
    assert [v.name for v in template_variables()] == [
        "description", "title", "video_url", "short_url", "video_id", "publish_date", "duration"]
