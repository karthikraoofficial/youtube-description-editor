"""Seam 1: no-op detection and Flags on a Proposed change."""
from app.domain.operations import FindReplace
from app.proposals import propose


def video(description):
    return {"id": "v", "title": "T", "description": description, "published_at": "2025-01-01T00:00:00Z",
            "duration_s": 60}


def test_a_matching_operation_is_a_change():
    p = propose(FindReplace(find="old", replace="new"), video("old link"))
    assert (p.changed, p.after, p.after_bytes) == (True, "new link", 8)


def test_no_match_is_a_no_op():
    p = propose(FindReplace(find="absent", replace="x"), video("old link"))
    assert (p.changed, p.after) == (False, "old link")


def test_replacing_text_with_itself_is_a_no_op():
    assert propose(FindReplace(find="link", replace="link"), video("old link")).changed is False


def test_only_changes_are_flagged():
    long_text = "a" * 5001
    assert propose(FindReplace(find="zzz", replace="y"), video(long_text)).flags == []
    [flag] = propose(FindReplace(find="a", replace="aa", regex=True), video("a" * 2600)).flags
    assert flag.code == "too_long"
