"""Common HTTP API response helpers."""

from __future__ import annotations

from typing import Any


def ok_response(result: Any | None = None, **extra: Any) -> dict[str, Any]:
    """Build a successful API response."""
    payload: dict[str, Any] = {"ok": True}
    if result is not None:
        payload["result"] = result
    payload.update(extra)
    return payload


def error_response(error_type: str, message: str) -> dict[str, Any]:
    """Build an error API response."""
    return {
        "ok": False,
        "error": {
            "type": error_type,
            "message": message,
        },
    }

