"""HTTP API request and response schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiEnvelope(BaseModel):
    """Generic API response envelope."""

    ok: bool
    result: Any | None = None
    error: dict[str, str] | None = None


class TrainJobCreateRequest(BaseModel):
    """Request body for creating an async training job."""

    model_config = ConfigDict(extra="forbid")

    request: dict[str, Any] = Field(
        description="Same payload accepted by train_model(request)."
    )


class TrainJobResult(BaseModel):
    """Training job status payload."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None


class ModelLoadCheckRequest(BaseModel):
    """Request body for checking whether a model can be loaded."""

    model_config = ConfigDict(extra="forbid")

    model_id: str | None = None
    model_path: str | None = None
    artifact_root: str | None = None


class ModelLoadCheckResult(BaseModel):
    """Result returned by model load-check endpoints."""

    model_config = ConfigDict(extra="forbid")

    loadable: bool
    model_id: str | None = None
    model_path: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

