from uuid import uuid4

from arq import create_pool
from arq.jobs import JobStatus
from arq.worker import Worker

from app.core.config import Settings
from app.workers.tasks import worker_settings


async def test_worker_runs_a_queued_noop_job(settings: Settings) -> None:
    # A queue of its own, so a dev worker on the same Redis can't take the job.
    queue = f"test:{uuid4()}"
    config = worker_settings(settings)
    pool = await create_pool(config["redis_settings"], default_queue_name=queue)
    try:
        job = await pool.enqueue_job("noop")
        assert job is not None

        worker = Worker(**{**config, "queue_name": queue, "burst": True})
        try:
            await worker.async_run()
        finally:
            await worker.close()

        assert await job.status() == JobStatus.complete
        assert await job.result(timeout=1) is None
        assert worker.jobs_complete == 1
        assert worker.jobs_failed == 0
    finally:
        await pool.aclose()
