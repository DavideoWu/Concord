"""Content hashing for fetched artifacts.

Invariant 6 (CLAUDE.md): every fetched artifact is content-hashed so re-runs are
idempotent and unchanged documents are never re-fetched or re-extracted.
"""

from __future__ import annotations

import hashlib


def hash_content(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
