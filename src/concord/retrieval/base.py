"""Base adapter interface for retrieval sources (CLAUDE.md layer 1: "adapters per source").

Each adapter implements only the source-specific HTTP call (`_get`); hashing, timestamping,
and the RetrievedDocument shape are handled once here so every source produces the same
typed output.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from concord.retrieval.hashing import hash_content
from concord.retrieval.models import RetrievalRequest, RetrievedDocument


class RetrievalAdapter(ABC):
    source_id: str

    @abstractmethod
    async def _get(self, url: str) -> tuple[bytes, str | None, int]:
        """Fetch raw bytes, content-type, and HTTP status for url.

        Raises RetrievalError on failure.
        """

    async def fetch(self, request: RetrievalRequest) -> RetrievedDocument:
        content, content_type, status = await self._get(str(request.url))
        return RetrievedDocument(
            source_id=self.source_id,
            url=request.url,
            content=content,
            content_type=content_type,
            content_hash=hash_content(content),
            http_status=status,
            fetched_at=datetime.now(UTC),
        )
