"""Settings for the HTTP API adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class ApiSettings:
    """Runtime settings for the FastAPI service."""

    host: str = "127.0.0.1"
    port: int = 8012
    artifact_root: Path = Path("artifacts/models")
    data_root: Path = Path("data")
    allow_absolute_paths: bool = True
    cors_origins: list[str] = field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )


def load_settings() -> ApiSettings:
    """Load API settings from environment variables."""
    cors_origins = os.environ.get("TRAINGLUONTS_API_CORS_ORIGINS")

    return ApiSettings(
        host=os.environ.get("TRAINGLUONTS_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("TRAINGLUONTS_API_PORT", "8012")),
        artifact_root=Path(
            os.environ.get("TRAINGLUONTS_API_ARTIFACT_ROOT", "artifacts/models")
        ),
        data_root=Path(os.environ.get("TRAINGLUONTS_API_DATA_ROOT", "data")),
        allow_absolute_paths=os.environ.get(
            "TRAINGLUONTS_API_ALLOW_ABSOLUTE_PATHS",
            "true",
        ).lower()
        not in {"0", "false", "no"},
        cors_origins=(
            _split_csv(cors_origins)
            if cors_origins is not None
            else [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]
        ),
    )
