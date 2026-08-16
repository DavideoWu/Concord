"""Typed boundary for the retrieval layer (CLAUDE.md layer 1).

RetrievedDocument is what gets handed to layer 2 (raw store) once it exists — retrieval
never writes to storage itself ("never reach two layers down").
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl


class RetrievalRequest(BaseModel):
    """What to fetch. Sources are manually inputted (non-goal: no scraping/discovery),
    so this is just a URL to a specific document."""

    url: HttpUrl


class RetrievedDocument(BaseModel):
    """What was fetched, typed and self-describing enough for layer 2 to dedup and store."""

    source_id: str
    url: HttpUrl
    content: bytes
    content_type: str | None
    content_hash: str
    http_status: int
    fetched_at: datetime
