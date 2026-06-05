"""Public training workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gluonts.evaluation import Evaluator, make_evaluation_predictions
from pydantic import ValidationError

from traingluonts.dataset import resolve_dataset, split_for_evaluation, to_list_dataset
from traingluonts.errors import ModelTrainingError, TrainingRequestError
from traingluonts.estimators import create_estimator
from traingluonts.registry import (
    build_metadata,
    create_model_id,
    prepare_model_dir,
    write_json,
)
from traingluonts.schemas import TrainingRequest, TrainingResult
from traingluonts.training import train_estimator_without_checkpoint_pruning


def train_model(request: TrainingRequest | dict[str, Any]) -> TrainingResult:
    """Train a GluonTS model and save it locally."""
    try:
        normalized = _normalize_request(request)
        model_id = create_model_id()
        model_dir = prepare_model_dir(normalized.artifact_root, model_id)

        write_json(model_dir / "request.json", normalized.model_dump(mode="json"))

        if normalized.evaluation.enabled:
            test_length = normalized.evaluation.test_length or (
                normalized.prediction_length
            )
            train_ds, test_ds = split_for_evaluation(
                normalized.dataset,
                normalized.freq,
                test_length,
            )
        else:
            train_ds = to_list_dataset(normalized.dataset, normalized.freq)
            test_ds = None

        estimator = create_estimator(normalized, model_dir)
        train_output = train_estimator_without_checkpoint_pruning(
            estimator,
            train_ds,
        )
        predictor = train_output.predictor

        metrics = None
        metrics_path = None
        if test_ds is not None:
            metrics = _evaluate(normalized, predictor, test_ds)
            metrics_path = model_dir / "metrics.json"
            write_json(metrics_path, metrics)

        predictor_dir = model_dir / "predictor"
        predictor_dir.mkdir(parents=True, exist_ok=True)
        predictor.serialize(predictor_dir)

        metadata = build_metadata(normalized, model_id, model_dir, metrics_path)
        write_json(model_dir / "metadata.json", metadata.model_dump(mode="json"))

        return TrainingResult(
            model_id=model_id,
            model_name=normalized.model_name,
            algorithm=normalized.algorithm,
            status="completed",
            model_path=str(predictor_dir),
            metadata_path=str(model_dir / "metadata.json"),
            metrics=metrics,
        )
    except ValidationError as exc:
        raise TrainingRequestError(str(exc)) from exc
    except TrainingRequestError:
        raise
    except Exception as exc:
        raise ModelTrainingError(str(exc)) from exc


def _normalize_request(request: TrainingRequest | dict[str, Any]) -> TrainingRequest:
    if isinstance(request, TrainingRequest):
        request.model_hyperparameters()
        return _with_resolved_dataset(request)

    normalized = TrainingRequest.model_validate(request)
    normalized.model_hyperparameters()
    return _with_resolved_dataset(normalized)


def _with_resolved_dataset(request: TrainingRequest) -> TrainingRequest:
    dataset = resolve_dataset(request.dataset)
    resolved = request.model_copy(update={"dataset": dataset})
    _validate_dataset_lengths(resolved)
    return resolved


def _validate_dataset_lengths(request: TrainingRequest) -> None:
    holdout = request.evaluation.test_length or request.prediction_length

    if request.evaluation.enabled:
        for item in request.dataset.series:
            if len(item.target) <= holdout:
                raise TrainingRequestError(
                    "each target length must be greater than evaluation test_length"
                )
    else:
        for item in request.dataset.series:
            if len(item.target) < request.prediction_length:
                raise TrainingRequestError(
                    "each target length must be at least prediction_length"
                )


def _evaluate(
    request: TrainingRequest,
    predictor,
    test_ds,
) -> dict[str, float]:
    forecast_it, ts_it = make_evaluation_predictions(
        dataset=test_ds,
        predictor=predictor,
        num_samples=request.evaluation.num_samples,
    )
    forecasts = list(forecast_it)
    time_series = list(ts_it)

    evaluator = Evaluator(quantiles=request.evaluation.quantiles)
    aggregate_metrics, _ = evaluator(time_series, forecasts)

    metric_names = ["MASE", "MAPE", "RMSE", "mean_wQuantileLoss"]
    return {
        metric_name: float(aggregate_metrics[metric_name])
        for metric_name in metric_names
        if metric_name in aggregate_metrics
    }
