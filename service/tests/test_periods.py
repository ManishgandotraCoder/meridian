import pytest

from meridian.periods import InvalidPeriod, resolve_period


def test_relative_periods_end_at_the_export_window():
    last_week = resolve_period("last_7_days")
    assert last_week.start.isoformat() == "2026-09-21"
    assert last_week.end_exclusive.isoformat() == "2026-09-28"
    last_monthish = resolve_period("last_30_days")
    assert last_monthish.start.isoformat() == "2026-08-29"
    assert last_monthish.end_exclusive.isoformat() == "2026-09-28"


def test_iso_week_and_month():
    week = resolve_period("2026-W32")
    assert week.start.isoformat() == "2026-08-03"
    assert week.end_exclusive.isoformat() == "2026-08-10"
    september = resolve_period("2026-09")
    assert september.start.isoformat() == "2026-09-01"
    assert september.end_exclusive.isoformat() == "2026-10-01"


@pytest.mark.parametrize("period", ["yesterday", "2026-W99", "2026-13", "2026-W3", ""])
def test_bad_periods(period):
    with pytest.raises(InvalidPeriod):
        resolve_period(period)
