import uuid
from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class DueReview(BaseModel):
    """One Vocab Item in the Review Queue: due on `due_on`, today or earlier."""

    vocab_item_id: uuid.UUID
    phrase: str
    translation: str
    scenario_title: str
    due_on: date


class ReviewQueue(BaseModel):
    """The Vocab Items due for Review on the User's local today or earlier, oldest
    first. Empty on the Event Day and for a Past Event."""

    count: int
    items: list[DueReview]


class Grade(StrEnum):
    """The User's four buttons on a Review. Only Again counts as forgotten."""

    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


class ReviewGrade(BaseModel):
    """What a User sends to grade one of today's Reviews."""

    vocab_item_id: uuid.UUID
    grade: Grade


class ReviewResult(BaseModel):
    """A graded item's next due date: null once nothing more is scheduled before the
    Event Day."""

    vocab_item_id: uuid.UUID
    due_on: date | None
