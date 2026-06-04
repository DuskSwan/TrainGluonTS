"""Estimator factory for supported GluonTS models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gluonts.torch.model.deepar import DeepAREstimator
from gluonts.torch.model.simple_feedforward import SimpleFeedForwardEstimator

from traingluonts.schemas import (
    DeepARHyperParameters,
    SimpleFeedForwardHyperParameters,
    TrainingRequest,
)


def create_estimator(request: TrainingRequest, output_dir: Path) -> Any:
    """Create a GluonTS estimator for the requested algorithm."""
    hyperparameters = request.model_hyperparameters()
    trainer_kwargs = _trainer_kwargs(request, output_dir)

    if request.algorithm == "deepar":
        assert isinstance(hyperparameters, DeepARHyperParameters)
        return DeepAREstimator(
            freq=request.freq,
            prediction_length=request.prediction_length,
            context_length=hyperparameters.context_length,
            num_layers=hyperparameters.num_layers,
            hidden_size=hyperparameters.hidden_size,
            dropout_rate=hyperparameters.dropout_rate,
            lr=hyperparameters.lr,
            weight_decay=hyperparameters.weight_decay,
            num_parallel_samples=hyperparameters.num_parallel_samples,
            nonnegative_pred_samples=hyperparameters.nonnegative_pred_samples,
            batch_size=request.training.batch_size,
            num_batches_per_epoch=request.training.num_batches_per_epoch,
            trainer_kwargs=trainer_kwargs,
        )

    if request.algorithm == "simple_feedforward":
        assert isinstance(hyperparameters, SimpleFeedForwardHyperParameters)
        return SimpleFeedForwardEstimator(
            prediction_length=request.prediction_length,
            context_length=hyperparameters.context_length,
            hidden_dimensions=hyperparameters.hidden_dimensions,
            lr=hyperparameters.lr,
            weight_decay=hyperparameters.weight_decay,
            batch_norm=hyperparameters.batch_norm,
            batch_size=request.training.batch_size,
            num_batches_per_epoch=request.training.num_batches_per_epoch,
            trainer_kwargs=trainer_kwargs,
        )

    raise ValueError(f"unsupported algorithm: {request.algorithm}")


def _trainer_kwargs(request: TrainingRequest, output_dir: Path) -> dict[str, Any]:
    return {
        "max_epochs": request.training.max_epochs,
        "accelerator": request.training.accelerator,
        "default_root_dir": str(output_dir),
        "enable_progress_bar": request.training.enable_progress_bar,
        "enable_model_summary": request.training.enable_model_summary,
        "logger": request.training.logger,
    }
