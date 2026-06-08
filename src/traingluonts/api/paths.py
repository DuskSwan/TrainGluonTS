"""Path normalization helpers for HTTP API requests."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from traingluonts.api.settings import ApiSettings
from traingluonts.errors import PredictionRequestError, TrainingRequestError


def normalize_training_request(
    payload: dict[str, Any],
    settings: ApiSettings,
) -> dict[str, Any]:
    """Normalize filesystem paths in a training request."""
    normalized = _normalize_common_paths(payload, settings, TrainingRequestError)
    if "artifact_root" not in normalized:
        normalized["artifact_root"] = str(settings.artifact_root.resolve())
    return normalized


def normalize_prediction_request(
    payload: dict[str, Any],
    settings: ApiSettings,
) -> dict[str, Any]:
    """Normalize filesystem paths in a prediction request."""
    normalized = _normalize_common_paths(payload, settings, PredictionRequestError)
    if "artifact_root" not in normalized:
        normalized["artifact_root"] = str(settings.artifact_root.resolve())
    return normalized


def normalize_model_reference(
    payload: dict[str, Any],
    settings: ApiSettings,
) -> dict[str, Any]:
    """Normalize paths in a model load-check payload."""
    normalized = copy.deepcopy(payload)
    _resolve_field(
        normalized,
        "artifact_root",
        Path.cwd(),
        settings,
        PredictionRequestError,
    )
    _resolve_field(
        normalized,
        "model_path",
        Path.cwd(),
        settings,
        PredictionRequestError,
    )
    return normalized


def _normalize_common_paths(
    payload: dict[str, Any],
    settings: ApiSettings,
    error_cls: type[Exception],
) -> dict[str, Any]:
    normalized = copy.deepcopy(payload)

    _resolve_field(normalized, "artifact_root", Path.cwd(), settings, error_cls)
    _resolve_field(normalized, "model_path", Path.cwd(), settings, error_cls)

    dataset = normalized.get("dataset")
    if isinstance(dataset, dict) and dataset.get("type") == "csv":
        _resolve_field(dataset, "path", settings.data_root, settings, error_cls)

    return normalized


def _resolve_field(
    container: dict[str, Any],
    field: str,
    base_dir: Path,
    settings: ApiSettings,
    error_cls: type[Exception],
) -> None:
    value = container.get(field)
    if not isinstance(value, str) or value == "":
        return

    path = Path(value).expanduser()
    if path.is_absolute():
        if not settings.allow_absolute_paths:
            raise error_cls(f"absolute paths are not allowed: {field}")
        container[field] = str(path.resolve())
        return

    container[field] = str((base_dir / path).resolve())
