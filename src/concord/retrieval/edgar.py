"""SEC EDGAR retrieval adapter — iteration 1's only source (CLAUDE.md).

EDGAR serves static HTML/XML/plain-text filings, so httpx is sufficient and Playwright is
never needed here. SEC's fair-access policy requires a descriptive User-Agent with contact
info and caps automated traffic at 10 req/s per host:
https://www.sec.gov/os/webmaster-faq#developers
"""

from __future__ import annotations

import asyncio
import os

#used like httpx.get(url)
import httpx

from concord.retrieval.base import RetrievalAdapter
from concord.retrieval.errors import RetrievalError
from concord.retrieval.rate_limit import RateLimiter

SOURCE_ID = "sec-edgar"

_DEFAULT_REQUESTS_PER_SECOND = 5.0
_DEFAULT_MAX_CONCURRENCY = 5
_MAX_ATTEMPTS = 3


class EdgarAdapter(RetrievalAdapter):
    source_id = SOURCE_ID

    def __init__(
        self,
        user_agent: str,
        client: httpx.AsyncClient | None = None, #async equivalent of requests.Session. Attached to client as same TCP/TLS connnection across many requests.
        requests_per_second: float = _DEFAULT_REQUESTS_PER_SECOND,
        max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("EdgarAdapter requires a non-empty SEC-compliant User-Agent")
        self._client = client or httpx.AsyncClient()
        self._client.headers["User-Agent"] = user_agent
        self._rate_limiter = RateLimiter(requests_per_second, max_concurrency)

    @classmethod
    def from_env(cls, **kwargs: object) -> EdgarAdapter:
        user_agent = os.environ.get("CONCORD_EDGAR_USER_AGENT")
        if not user_agent:
            raise RuntimeError(
                "CONCORD_EDGAR_USER_AGENT is not set. SEC EDGAR requires a descriptive "
                "User-Agent with contact info, e.g. 'Concord/0.1 (you@example.com)'."
            )
        return cls(user_agent=user_agent, **kwargs)  # type: ignore[arg-type]

    #close TCP connection with SEC-EDGAR
    async def aclose(self) -> None:
        await self._client.aclose()

    #implement abstract method _get
    async def _get(self, url: str) -> tuple[bytes, str | None, int]:
        for attempt in range(_MAX_ATTEMPTS):
            async with self._rate_limiter:
                response = await self._client.get(url)

            if response.status_code == 429 and attempt < _MAX_ATTEMPTS - 1:
                retry_after = float(response.headers.get("Retry-After", 2**attempt))
                await asyncio.sleep(retry_after)
                continue

            if response.status_code >= 400:
                raise RetrievalError(
                    f"failed to fetch {url} (status {response.status_code})",
                    url=url,
                    status_code=response.status_code,
                )

            return response.content, response.headers.get("content-type"), response.status_code

        raise RetrievalError(f"exhausted retries fetching {url}", url=url, status_code=429)
