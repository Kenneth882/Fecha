from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from hypothesis import given
from hypothesis import strategies as st

from app.services.local_time import local_today

# Real offsets run from UTC-12 to UTC+14, so a local date is never more than a day
# either side of the UTC date.
moments = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 1, 1),
    timezones=st.just(UTC),
)


@given(moment=moments, timezone=st.timezones())
def test_local_today_is_within_a_day_of_the_utc_date(moment: datetime, timezone: ZoneInfo) -> None:
    today = local_today(moment, timezone.key)

    assert abs(today - moment.date()) <= timedelta(days=1)
