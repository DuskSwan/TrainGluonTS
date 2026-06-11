"""Model inspection routes."""

from __future__ import annotations

import os
import re
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request

from traingluonts.api.paths import normalize_model_reference
from traingluonts.api.responses import ok_response
from traingluonts.api.schemas import (
    ModelLoadCheckRequest,
    ModelLoadCheckResult,
    ModelPublishRequest,
    ModelPublishResult,
)
from traingluonts.errors import PredictionRequestError
from traingluonts.inference import resolve_predictor_path
from traingluonts.registry import load_model
from traingluonts.schemas import PredictionRequest


router = APIRouter(tags=["models"])
_VERSION_UNSAFE_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


@router.post("/models/load-check")
def load_check(request: Request, payload: ModelLoadCheckRequest) -> dict:
    """Check whether a model path or model id can be loaded."""
    settings = request.app.state.settings
    normalized = normalize_model_reference(payload.model_dump(exclude_none=True), settings)
    model_path = _load_and_resolve_path(normalized, settings.artifact_root)

    result = ModelLoadCheckResult(
        loadable=True,
        model_id=normalized.get("model_id"),
        model_path=str(model_path),
        checked_at=datetime.now(timezone.utc),
    )
    return ok_response(result.model_dump(mode="json"))


@router.get("/models/{model_id}/load-check")
def load_check_by_model_id(request: Request, model_id: str) -> dict:
    """Check whether a model id can be loaded from configured artifact_root."""
    settings = request.app.state.settings
    payload = {
        "model_id": model_id,
        "artifact_root": str(settings.artifact_root),
    }
    normalized = normalize_model_reference(payload, settings)
    model_path = _load_and_resolve_path(normalized, settings.artifact_root)

    result = ModelLoadCheckResult(
        loadable=True,
        model_id=model_id,
        model_path=str(model_path),
        checked_at=datetime.now(timezone.utc),
    )
    return ok_response(result.model_dump(mode="json"))


@router.post("/models/publish")
def publish_model(request: Request, payload: ModelPublishRequest) -> dict:
    """Publish a trained model by copying it to the configured publish root."""
    settings = request.app.state.settings
    artifact_root = settings.artifact_root.resolve()
    source_dir = (artifact_root / payload.model_id).resolve()
    if artifact_root not in source_dir.parents:
        return _publish_response(
            code=400,
            message="model_id resolves outside artifact root",
        )

    if not source_dir.exists() or not (source_dir / "predictor").exists():
        return _publish_response(
            code=404,
            message=f"model_id not found in artifact root: {payload.model_id}",
        )

    version = _sanitize_version(payload.version)
    if not version:
        return _publish_response(
            code=400,
            message="version is empty after sanitization",
        )

    target_dir = (settings.publish_root / str(payload.user_id) / version).resolve()
    publish_root = settings.publish_root.resolve()
    if publish_root not in target_dir.parents:
        return _publish_response(
            code=400,
            message="publish path is outside publish root",
        )

    _sync_copy_tree(source_dir, target_dir)

    result = ModelPublishResult(path=str(target_dir))
    return _publish_response(
        code=0,
        message="success",
        data=result.model_dump(mode="json"),
    )


def _load_and_resolve_path(payload: dict, default_artifact_root: Path) -> Path:
    artifact_root = Path(payload.get("artifact_root", default_artifact_root))

    if "model_path" in payload:
        model_reference = payload["model_path"]
        load_model(model_reference)
        return Path(model_reference).resolve()

    if "model_id" not in payload:
        raise PredictionRequestError("either model_id or model_path must be provided")

    model_id = payload["model_id"]
    load_model(model_id, artifact_root)
    prediction_request = PredictionRequest.model_validate(
        {
            "model_id": model_id,
            "artifact_root": str(artifact_root),
            "dataset": {
                "series": [
                    {
                        "item_id": "load_check",
                        "start": "2024-01-01",
                        "target": [0.0],
                    }
                ]
            },
            "freq": "D",
        }
    )
    return resolve_predictor_path(prediction_request)


def _sanitize_version(version: str) -> str:
    sanitized = _VERSION_UNSAFE_PATTERN.sub("_", version.strip())
    sanitized = re.sub(r"_+", "_", sanitized)
    return sanitized.strip(" ._")


def _sync_copy_tree(source_dir: Path, target_dir: Path) -> None:
    if target_dir.exists():
        try:
            _remove_tree(target_dir)
        except OSError:
            pass

    shutil.copytree(
        source_dir,
        target_dir,
        copy_function=_copy_file,
        dirs_exist_ok=target_dir.exists(),
    )


def _copy_file(source_path: str | Path, target_path: str | Path) -> str:
    source = Path(source_path)
    target = Path(target_path)
    try:
        shutil.copy2(source, target)
    except PermissionError:
        os.chmod(target, stat.S_IWRITE)
        shutil.copy2(source, target)
    return str(target)


def _remove_tree(path: Path) -> None:
    def make_writable_and_retry(function, value, exc_info) -> None:
        os.chmod(value, stat.S_IWRITE)
        function(value)

    shutil.rmtree(path, onerror=make_writable_and_retry)


def _publish_response(
    *,
    code: int,
    message: str,
    data: dict | None = None,
) -> dict:
    return {
        "code": code,
        "message": message,
        "data": data if data is not None else {},
    }
