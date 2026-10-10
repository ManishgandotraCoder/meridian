"""Period windows. Relative periods end at the export window, not the wall clock."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from meridian.config import DATA_AS_OF

_PERIOD = re.compile(r"^(last_7_days|last_30_days|\d{4}-W\d{2}|\d{4}-\d{2})$")
_AS_OF = date.fromisoformat(DATA_AS_OF)


@dataclass(frozen=True)
class Window:
    start: date
    end_exclusive: date

    def as_dict(self) -> dict:
        return {"start": self.start.isoformat(), "end_exclusive": self.end_exclusive.isoformat()}

    def contains(self, day: str) -> bool:
        current = date.fromisoformat(day)
        return self.start <= current < self.end_exclusive


class InvalidPeriod(ValueError):
    pass


def resolve_period(period: str, as_of: Optional[date] = None) -> Window:
    if not isinstance(period, str) or not _PERIOD.match(period):
        raise InvalidPeriod(
            "period must be last_7_days, last_30_days, an ISO week (2026-W36), or a month (2026-09)."
        )
    anchor = as_of or _AS_OF
    if period == "last_7_days":
        return Window(anchor - timedelta(days=7), anchor)
    if period == "last_30_days":
        return Window(anchor - timedelta(days=30), anchor)
    if "-W" in period:
        year_s, week_s = period.split("-W")
        try:
            start = date.fromisocalendar(int(year_s), int(week_s), 1)
        except ValueError as exc:
            raise InvalidPeriod("%s is not a real ISO week." % period) from exc
        return Window(start, start + timedelta(days=7))
    year_s, month_s = period.split("-")
    year, month = int(year_s), int(month_s)
    if month < 1 or month > 12:
        raise InvalidPeriod("%s is not a real month." % period)
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return Window(start, end)


def iso_week(day: str) -> str:
    year, week, _ = date.fromisoformat(day).isocalendar()
    return "%d-W%02d" % (year, week)
