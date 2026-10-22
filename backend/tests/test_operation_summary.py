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
