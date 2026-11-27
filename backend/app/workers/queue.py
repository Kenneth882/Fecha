"""Queuing the worker's jobs from the API.

Routes get a `JobQueue` through `Depends(get_job_queue)`; tests swap in a fake.
"""

import uuid
from typing import Protocol

from arq.connections import ArqRedis

# The job's name in the worker (`app.workers.tasks.generate_event_content`).
GENERATE_EVENT_CONTENT = "generate_event_content"


def event_content_job_id(event_id: uuid.UUID) -> str:
    """The Event's content job ID. arq won't queue a second job with an ID that's
    already queued or running, so one Event's job never runs twice at once."""
    return f"{GENERATE_EVENT_CONTENT}:{event_id}"


class JobQueue(Protocol):
    async def enqueue_event_content(self, event_id: uuid.UUID) -> bool:
        """Queue the Event's content job, unless it's already queued or running.
        Returns whether it was queued."""
        ...


class ArqJobQueue:
    """Queues jobs on the arq worker's Redis queue."""

    def __init__(self, redis: ArqRedis) -> None:
        self._redis = redis

    async def enqueue_event_content(self, event_id: uuid.UUID) -> bool:
        job = await self._redis.enqueue_job(
            GENERATE_EVENT_CONTENT, str(event_id), _job_id=event_content_job_id(event_id)
        )
        return job is not None
