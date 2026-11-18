"""SQLAlchemy tables. Import every model module here so `Base.metadata` sees it."""

from app.models.base import Base
from app.models.event import Event, Milestone, Plan, Task, VocabTaskItem
from app.models.review import Review, ReviewState
from app.models.user import Role, User
from app.models.vocab import VocabItem, VocabSource

__all__ = [
    "Base",
    "Event",
    "Milestone",
    "Plan",
    "Review",
    "ReviewState",
    "Role",
    "Task",
    "User",
    "VocabItem",
    "VocabSource",
    "VocabTaskItem",
]
