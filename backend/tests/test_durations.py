import pytest

from app.youtube.google import parse_iso_duration


@pytest.mark.parametrize("iso,seconds", [
    ("PT45S", 45),
    ("PT3M", 180),
    ("PT1H2M3S", 3723),
    ("P1DT2H", 93600),
    ("P1W", 604800),
    ("P0D", 0),
    ("PT0S", 0),
])
def test_iso_durations_parse_to_seconds(iso, seconds):
    assert parse_iso_duration(iso) == seconds


def test_unparseable_duration_is_zero():
    assert parse_iso_duration("garbage") == 0
