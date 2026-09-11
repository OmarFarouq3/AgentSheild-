"""Request-local transport isolation and document fixtures for adaptive tests.

This is an evaluation boundary, not a target defense. Context variables keep
concurrent chat requests and campaigns independent without monkeypatching tools.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from typing import Iterator
from urllib.parse import urlsplit

_active: ContextVar[bool] = ContextVar("adaptive_evaluation_active", default=False)
_payload: ContextVar[str | None] = ContextVar("adaptive_document_payload", default=None)
SYNTHETIC_TOOLS = frozenset({"read_partner_brief", "read_confidential_document"})


def validate_model_endpoint(url: str) -> None:
    """Permit local Ollama and the repository's private Compose service only."""

    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1", "ollama"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("Adaptive tests require local Ollama or the private Compose ollama service.")


def intercept_tool(tool_name: str) -> bool:
    return _active.get() and tool_name not in SYNTHETIC_TOOLS


def document_payload() -> str | None:
    return _payload.get() if _active.get() else None


def payload_hash(payload: str) -> str:
    return sha256(payload.encode("utf-8")).hexdigest()


@contextmanager
def adaptive_evaluation_scope(payload: str | None = None) -> Iterator[None]:
    active_token = _active.set(True)
    payload_token = _payload.set(payload)
    try:
        yield
    finally:
        _payload.reset(payload_token)
        _active.reset(active_token)
