from __future__ import annotations


class RetrievalError(Exception):
    """Raised when a source can't be fetched (non-2xx after retries, etc.)."""

    def __init__(self, message: str, *, url: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code
