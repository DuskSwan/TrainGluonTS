"""Health and version routes."""

from __future__ import annotations

from fastapi import APIRouter

from traingluonts import __version__
from traingluonts.api.responses import ok_response


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """Return service health status."""
    return ok_response({"status": "healthy"})


@router.get("/version")
def version() -> dict:
    """Return package version."""
    return ok_response({"version": __version__})

