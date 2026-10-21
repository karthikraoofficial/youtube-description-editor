from datetime import datetime, timezone

from app.quota import next_reset, pacific_date


def test_quota_day_follows_pacific_time_not_utc():
    # 06:59 UTC on 22 Oct is 23:59 on 21 Oct in Pacific time (PDT, UTC-7); 07:00 UTC is midnight.
    assert pacific_date(datetime(2026, 10, 22, 6, 59, tzinfo=timezone.utc)) == "2026-10-21"
    assert pacific_date(datetime(2026, 10, 22, 7, 0, tzinfo=timezone.utc)) == "2026-10-22"


def test_quota_resets_at_the_next_pacific_midnight():
    assert next_reset(datetime(2026, 10, 22, 6, 59, tzinfo=timezone.utc)).isoformat() == "2026-10-22T00:00:00-07:00"
    # Winter time (PST, UTC-8)
    assert next_reset(datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)).isoformat() == "2026-12-02T00:00:00-08:00"
