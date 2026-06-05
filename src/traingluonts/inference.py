"""Public prediction workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import ValidationError

from traingluonts.dataset import resolve_dataset, to_list_dataset
from traingluonts.errors import (
    ModelPredictionError,
    ModelRegistryError,
    PredictionRequestError,
)
from traingluonts.registry import load_model
from traingluonts.schemas import (
    ForecastResult,
    PredictionRequest,
    PredictionResult,
)


def predict(request: PredictionRequest | dict[str, Any]) -> PredictionResult:
    """Load a saved predictor and forecast the provided time series."""
    try:
        normalized = _normalize_request(request)
        predictor_path = resolve_predictor_path(normalized)
        predictor = load_model(predictor_path)
        freq = resolve_dataset_freq(normalized, predictor_path)
        dataset = to_list_dataset(normalized.dataset, freq)

        forecasts = list(
            predictor.predict(
                dataset,
                num_samples=normalized.prediction.num_samples,
            )
        )

        return PredictionResult(
            model_id=normalized.model_id,
            model_path=str(predictor_path),
            forecasts=[
                _forecast_to_result(
                    forecast,
                    normalized.prediction.quantiles,
                )
                for forecast in forecasts
            ],
        )
    except ValidationError as exc:
        raise PredictionRequestError(str(exc)) from exc
    except (PredictionRequestError, ModelRegistryError):
        raise
    except Exception as exc:
        raise ModelPredictionError(str(exc)) from exc


def load_predictor(model_id: str, artifact_root: str | Path = "artifacts/models"):
    """Load a predictor by model id."""
    return load_model(model_id, Path(artifact_root))


def predict_with_model(
    model_path: str | Path,
    dataset,
    *,
    freq: str | None = None,
    num_samples: int = 100,
    quantiles: list[float] | None = None,
) -> PredictionResult:
    """Predict from an explicit serialized predictor path."""
    request = PredictionRequest(
        model_path=Path(model_path),
        freq=freq,
        dataset=dataset,
        prediction={
            "num_samples": num_samples,
            "quantiles": quantiles or [0.1, 0.5, 0.9],
        },
    )
    return predict(request)


def resolve_predictor_path(request: PredictionRequest) -> Path:
    """Resolve a prediction request to a serialized predictor directory."""
    if request.model_path is not None:
        path = request.model_path
    else:
        assert request.model_id is not None
        path = request.artifact_root / request.model_id / "predictor"

    return path.resolve()


def resolve_dataset_freq(request: PredictionRequest, predictor_path: Path) -> str:
    """Resolve the dataset frequency needed by GluonTS ListDataset."""
    if request.freq is not None:
        return request.freq

    training_request_path = _training_request_path(request, predictor_path)
    if training_request_path is not None and training_request_path.exists():
        payload = json.loads(training_request_path.read_text(encoding="utf-8"))
        freq = payload.get("freq")
        if isinstance(freq, str) and freq:
            return freq

    raise PredictionRequestError(
        "freq is required when request.json cannot be found next to the model"
    )


def _normalize_request(
    request: PredictionRequest | dict[str, Any],
) -> PredictionRequest:
    if isinstance(request, PredictionRequest):
        normalized = request
    else:
        normalized = PredictionRequest.model_validate(request)

    try:
        dataset = resolve_dataset(normalized.dataset)
    except (OSError, ValueError) as exc:
        raise PredictionRequestError(str(exc)) from exc

    return normalized.model_copy(update={"dataset": dataset})


def _training_request_path(
    request: PredictionRequest,
    predictor_path: Path,
) -> Path | None:
    if request.model_id is not None:
        return (request.artifact_root / request.model_id / "request.json").resolve()

    if predictor_path.name == "predictor":
        return predictor_path.parent / "request.json"

    return None


def _forecast_to_result(forecast, quantiles: list[float]) -> ForecastResult:
    return ForecastResult(
        item_id=forecast.item_id,
        start_date=str(forecast.start_date),
        mean=_to_float_list(forecast.mean),
        quantiles={
            _format_quantile(quantile): _to_float_list(forecast.quantile(quantile))
            for quantile in quantiles
        },
    )


def _format_quantile(value: float) -> str:
    return f"{value:g}"


def _to_float_list(values) -> list[float]:
    return [float(item) for item in np.asarray(values).tolist()]
