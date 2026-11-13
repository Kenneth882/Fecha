"""A Task's status, derived from its completion and Plan Day rather than stored.

Pure: no I/O and no hidden "now". Callers pass the User's local today, from
`local_today`. Like an Event's state (ADR 0005), a Task turns Missed at the User's
local midnight without any write.
"""

from datetime import date, datetime
from enum import StrEnum


class TaskStatus(StrEnum):
    """Where a Task stands on the User's local today."""

    PENDING = "pending"
    COMPLETED = "completed"
    MISSED = "missed"


def task_status(task_date: date, completed_at: datetime | None, *, today: date) -> TaskStatus:
    """`completed` once done; `missed` if still not done after its Plan Day ended;
    otherwise `pending`."""
    if completed_at is not None:
        return TaskStatus.COMPLETED
    if task_date < today:
        return TaskStatus.MISSED
    return TaskStatus.PENDING
