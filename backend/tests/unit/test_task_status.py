from datetime import UTC, date, datetime

import pytest

from app.services.task_status import TaskStatus, task_status

TODAY = date(2026, 11, 10)
DONE = datetime(2026, 11, 9, 18, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("task_date", "completed_at", "expected"),
    [
        # An incomplete Task becomes Missed once its Plan Day has ended...
        (date(2026, 11, 9), None, TaskStatus.MISSED),
        # ...but not while its Plan Day is still today, or before it comes.
        (TODAY, None, TaskStatus.PENDING),
        (date(2026, 11, 11), None, TaskStatus.PENDING),
        # A completed Task stays completed, whenever its Plan Day was.
        (date(2026, 11, 9), DONE, TaskStatus.COMPLETED),
        (TODAY, DONE, TaskStatus.COMPLETED),
    ],
)
def test_a_tasks_status_follows_its_completion_and_plan_day(
    task_date: date, completed_at: datetime | None, expected: TaskStatus
) -> None:
    assert task_status(task_date, completed_at, today=TODAY) is expected
