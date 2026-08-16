"""Async rate limiter — caps concurrency and request rate for a source.

Stack convention (CLAUDE.md): "semaphores to cap concurrency." SEC EDGAR's fair-access
policy additionally caps automated traffic at 10 req/s per host, so this also enforces a
minimum interval between request starts, not just a concurrency ceiling.
"""

from __future__ import annotations

import asyncio
import time
from types import TracebackType


class RateLimiter:
    def __init__(self, requests_per_second: float, max_concurrency: int) -> None:
        self._min_interval = 1.0 / requests_per_second
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def __aenter__(self) -> RateLimiter:
        await self._semaphore.acquire()
        async with self._lock:
            now = time.monotonic()
            wait = self._last_request_at + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._semaphore.release()
