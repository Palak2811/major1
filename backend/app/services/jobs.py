"""Background job dispatch.

With REDIS_URL set, jobs go to Celery (Redis broker) and run in the worker process.
Without Redis (default local setup), they run as asyncio tasks *after* the HTTP response is
sent. Either way the request thread never waits on Judge0.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.db import SessionLocal

log = logging.getLogger(__name__)

_registry: dict[str, Callable[..., Awaitable[None]]] = {}
_pending: set[asyncio.Task] = set()
_deferred: list[tuple[str, dict]] = []
# Tests set this so jobs start only when drain() is called, i.e. strictly after the request
# that enqueued them has finished (as in production, where they run in another process/connection).
defer = False
session_factory: async_sessionmaker[AsyncSession] = SessionLocal


def job(name: str):
    def deco(fn: Callable[..., Awaitable[None]]):
        _registry[name] = fn
        return fn
    return deco


async def run(name: str, **kwargs) -> None:
    try:
        await _registry[name](**kwargs)
    except Exception:  # never crash the loop; the job records its own failure state
        log.exception("job %s failed", name)


def enqueue(name: str, **kwargs) -> None:
    if get_settings().redis_url:
        from app.worker import celery_app

        celery_app.send_task("jobs.run", kwargs={"name": name, "kwargs": kwargs})
        return
    if defer:
        _deferred.append((name, kwargs))
        return
    task = asyncio.get_running_loop().create_task(run(name, **kwargs))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def drain() -> None:
    """Run deferred jobs and wait for in-process ones (used by tests)."""
    while _deferred:
        name, kwargs = _deferred.pop(0)
        await run(name, **kwargs)
    while _pending:
        await asyncio.gather(*list(_pending), return_exceptions=True)
