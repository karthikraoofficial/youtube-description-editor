"""Seam 1: one-line summaries of Operations for History."""
from app.domain.operations import Append, FindReplace, Prepend, Section, Template, summarize


def test_each_operation_reads_as_a_short_sentence():
    assert summarize(FindReplace(find="old.link", replace="new.link")) == 'Replace "old.link" with "new.link"'
    assert summarize(FindReplace(find=r"\d+", replace="", regex=True)) == 'Replace regex "\d+" with ""'
    assert summarize(Append(text="Guitar lessons: https://x.example")) == (
        'Append to Description: "Guitar lessons: https://x.example"')
    assert summarize(Prepend(text="NEW ALBUM")) == 'Prepend: "NEW ALBUM"'
    assert summarize(Template(template="{description}\n\nWatch: {video_url}")) == 'Template: "{description} …"'
    assert summarize(Section(start_marker="[L]", end_marker="[/L]", content="x")) == "Section between [L] and [/L]"


def test_long_text_is_shortened_to_its_first_line():
    s = summarize(Append(text="A" * 80 + "\nsecond line"))
    assert s == 'Append to Description: "' + "A" * 40 + '…"'


def test_summaries_on_other_fields_say_which_field_they_changed():
    from app.domain.fields import spec

    title = spec("title")
    assert summarize(Append(text="Guitar", separator="pipe"), title) == 'Append to Title: "Guitar"'
    assert summarize(Prepend(text="Live", separator="dash"), title) == 'Prepend to Title: "Live"'
    assert summarize(FindReplace(find="a", replace="b"), title) == 'Replace "a" with "b" in titles'
