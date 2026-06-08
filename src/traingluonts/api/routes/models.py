"""Model inspection routes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request

from traingluonts.api.paths import normalize_model_reference
from traingluonts.api.responses import ok_response
from traingluonts.api.schemas import ModelLoadCheckRequest, ModelLoadCheckResult
from traingluonts.errors import PredictionRequestError
from traingluonts.inference import resolve_predictor_path
from traingluonts.registry import load_model
from traingluonts.schemas import PredictionRequest


router = APIRouter(tags=["models"])


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
