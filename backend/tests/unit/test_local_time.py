from datetime import UTC, date, datetime

import pytest

from app.services.local_time import local_today

# Mexico City is UTC-6 all year (no DST since 2022), so local midnight is 06:00 UTC.
MEXICO_CITY = "America/Mexico_City"
# Tokyo is UTC+9, so local midnight is 15:00 UTC the day before.
TOKYO = "Asia/Tokyo"


@pytest.mark.parametrize(
    ("moment", "timezone", "expected"),
    [
        # 23:30 local on 9 Nov is already 05:30 UTC on 10 Nov.
        (datetime(2026, 11, 10, 5, 30, tzinfo=UTC), MEXICO_CITY, date(2026, 11, 9)),
        # 00:30 local on 10 Nov is 06:30 UTC on 10 Nov.
        (datetime(2026, 11, 10, 6, 30, tzinfo=UTC), MEXICO_CITY, date(2026, 11, 10)),
        # 23:30 local on 10 Nov is still 14:30 UTC on 10 Nov.
        (datetime(2026, 11, 10, 14, 30, tzinfo=UTC), TOKYO, date(2026, 11, 10)),
        # 00:30 local on 11 Nov is only 15:30 UTC on 10 Nov.
        (datetime(2026, 11, 10, 15, 30, tzinfo=UTC), TOKYO, date(2026, 11, 11)),
    ],
)
def test_local_today_is_the_date_on_the_users_wall_clock(
    moment: datetime, timezone: str, expected: date
) -> None:
    assert local_today(moment, timezone) == expected


def test_local_today_refuses_a_naive_moment() -> None:
    # A naive datetime would silently be read as the server's local time.
    with pytest.raises(ValueError, match="timezone-aware"):
        local_today(datetime(2026, 11, 10, 5, 30), MEXICO_CITY)
