"""Celery worker (used when REDIS_URL is set).

Run: celery -A app.worker.celery_app worker --pool=solo --loglevel=info   (solo pool on Windows)
Without Redis, jobs run in-process after the response instead (see app/services/jobs.py).
"""

import asyncio

from celery import Celery

from app.core.config import get_settings

_redis = get_settings().redis_url
celery_app = Celery("preppath", broker=_redis or "memory://", backend=_redis or "cache+memory://")
celery_app.conf.update(task_acks_late=True, worker_prefetch_multiplier=1)


@celery_app.task(name="system.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="jobs.run")
def run_job(name: str, kwargs: dict) -> None:
    import app.services.career  # noqa: F401  (registers jobs)
    import app.services.generation  # noqa: F401
    import app.services.judging  # noqa: F401
    import app.services.rag  # noqa: F401
    from app.services import jobs

    asyncio.run(jobs.run(name, **kwargs))
