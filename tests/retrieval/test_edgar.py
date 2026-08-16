"""Offline tests for the EDGAR retrieval adapter — no real network calls (CLAUDE.md)."""

from __future__ import annotations

import hashlib

import httpx
import pytest

from concord.retrieval import EdgarAdapter, RetrievalError, RetrievalRequest

TEST_URL = "https://www.sec.gov/Archives/edgar/data/1/1/doc.htm"


def _mock_client(**response_kwargs: object) -> httpx.AsyncClient:
    transport = httpx.MockTransport(lambda request: httpx.Response(**response_kwargs))  # type: ignore[arg-type]
    return httpx.AsyncClient(transport=transport)


async def test_fetch_returns_typed_document_with_content_hash() -> None:
    body = b"<html>fake filing</html>"
    client = _mock_client(status_code=200, content=body, headers={"content-type": "text/html"})
    adapter = EdgarAdapter(user_agent="Concord/0.1 (test@example.com)", client=client)

    doc = await adapter.fetch(RetrievalRequest(url=TEST_URL))

    assert doc.source_id == "sec-edgar"
    assert doc.content == body
    assert doc.content_type == "text/html"
    assert doc.http_status == 200
    assert doc.content_hash == hashlib.sha256(body).hexdigest()


async def test_fetch_sends_configured_user_agent() -> None:
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, content=b"ok")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = EdgarAdapter(user_agent="Concord/0.1 (test@example.com)", client=client)

    await adapter.fetch(RetrievalRequest(url=TEST_URL))

    assert seen_headers["user-agent"] == "Concord/0.1 (test@example.com)"


async def test_fetch_raises_on_client_error() -> None:
    client = _mock_client(status_code=404)
    adapter = EdgarAdapter(user_agent="Concord/0.1 (test@example.com)", client=client)

    with pytest.raises(RetrievalError):
        await adapter.fetch(RetrievalRequest(url=TEST_URL))


async def test_fetch_retries_on_429_then_succeeds() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, content=b"ok")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = EdgarAdapter(
        user_agent="Concord/0.1 (test@example.com)",
        client=client,
        requests_per_second=1000,
    )

    doc = await adapter.fetch(RetrievalRequest(url=TEST_URL))

    assert doc.content == b"ok"
    assert calls["count"] == 2


def test_from_env_requires_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONCORD_EDGAR_USER_AGENT", raising=False)
    with pytest.raises(RuntimeError):
        EdgarAdapter.from_env()


def test_rejects_blank_user_agent() -> None:
    with pytest.raises(ValueError):
        EdgarAdapter(user_agent="   ")
