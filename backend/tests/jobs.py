"""A fake job queue for API tests, so no test queues a real arq job."""

import uuid


class FakeJobQueue:
    """Records the Events whose content jobs were queued. Set `failing` to make
    queuing raise, as it would with Redis down."""

    def __init__(self) -> None:
        self.event_content: list[uuid.UUID] = []
        self.failing = False

    async def enqueue_event_content(self, event_id: uuid.UUID) -> bool:
        if self.failing:
            raise ConnectionError("Redis is down")
        self.event_content.append(event_id)
        return True
