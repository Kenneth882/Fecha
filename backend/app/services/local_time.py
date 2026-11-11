"""Turning a UTC moment into a User's local calendar date.

Pure: no I/O and no hidden "now". Callers pass the moment, usually from the
`get_now` clock dependency.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo


def local_today(moment: datetime, timezone: str) -> date:
    """The date on the wall clock in `timezone` (an IANA name) at `moment`.

    Plan Days, the Event Day (nothing is scheduled on or after it) and whether an
    Event is Active or Past are all judged by this local date, not the UTC one.
    `moment` must be timezone-aware; `timezone` must be a valid IANA name, as
    validated when the User registers.
    """
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    return moment.astimezone(ZoneInfo(timezone)).date()
