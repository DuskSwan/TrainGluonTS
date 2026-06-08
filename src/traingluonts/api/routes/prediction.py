"""Prediction routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from traingluonts.api.paths import normalize_prediction_request
from traingluonts.api.responses import ok_response
from traingluonts.errors import PredictionRequestError
from traingluonts.inference import predict, predict_with_model


router = APIRouter(tags=["prediction"])


@router.post("/predict")
def run_prediction(request: Request, payload: dict[str, Any]) -> dict:
    """Run prediction from a PredictionRequest-compatible payload."""
    settings = request.app.state.settings
    normalized = normalize_prediction_request(payload, settings)
    result = predict(normalized)
    return ok_response(result.model_dump(mode="json"))


@router.post("/predict-with-model")
def run_prediction_with_model(request: Request, payload: dict[str, Any]) -> dict:
    """Run prediction from an explicit model path."""
    settings = request.app.state.settings
    normalized = normalize_prediction_request(payload, settings)
    if "model_path" not in normalized:
        raise PredictionRequestError("model_path is required")

    model_path = normalized.pop("model_path")
    dataset = normalized.pop("dataset")
    prediction = normalized.pop("prediction", {}) or {}

    result = predict_with_model(
        model_path,
        dataset,
        freq=normalized.get("freq"),
        num_samples=prediction.get("num_samples", 100),
        quantiles=prediction.get("quantiles"),
    )
    return ok_response(result.model_dump(mode="json"))
