import uuid

from pydantic import BaseModel

from app.services.task_status import TaskStatus


class VocabBatchItem(BaseModel):
    """One Vocab Item in a Vocab Task's batch, with its English translation."""

    id: uuid.UUID
    phrase: str
    translation: str


class VocabBatch(BaseModel):
    """A Vocab Task's batch, in order. Fixed the first time the Task is opened or
    completed, so it's the same every time. It's shorter than the Task's
    `vocab_batch_size`, possibly empty, when its Scenario has run out of items."""

    task_id: uuid.UUID
    items: list[VocabBatchItem]


class TaskCompletion(BaseModel):
    """A completed Task's status, and how many Vocab Items it introduced.

    The same every time it's completed: a repeat changes nothing.
    """

    task_id: uuid.UUID
    status: TaskStatus
    items_introduced: int
