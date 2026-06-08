"""Synthetic data generation for examples and tests."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def generate_synthetic_series(
    *,
    num_series: int = 8,
    length: int = 120,
    start: str = "2024-01-01",
    seed: int = 7,
) -> list[dict[str, Any]]:
    """Generate deterministic univariate time series."""
    rng = np.random.default_rng(seed)
    series = []

    for item_id in range(num_series):
        time = np.arange(length)
        weekly_pattern = 4.0 * np.sin(2 * math.pi * time / 7)
        trend = 0.08 * time
        level = 20 + item_id * 3
        noise = rng.normal(loc=0.0, scale=0.8, size=time.shape)
        target = level + trend + weekly_pattern + noise

        series.append(
            {
                "item_id": f"series_{item_id}",
                "start": start,
                "target": target.astype(float).round(4).tolist(),
            }
        )

    return series


def generate_training_request(
    *,
    algorithm: str = "deepar",
    model_name: str | None = None,
    freq: str = "D",
    prediction_length: int = 7,
    context_length: int = 14,
    num_series: int = 4,
    length: int = 60,
    max_epochs: int = 1,
    num_batches_per_epoch: int = 2,
    batch_size: int = 8,
    artifact_root: str = "artifacts/test_models",
) -> dict[str, Any]:
    """Create a small request suitable for local tests."""
    hyperparameters: dict[str, Any]
    if algorithm == "deepar":
        hyperparameters = {
            "context_length": context_length,
            "num_layers": 1,
            "hidden_size": 8,
            "dropout_rate": 0.0,
        }
    elif algorithm == "simple_feedforward":
        hyperparameters = {
            "context_length": context_length,
            "hidden_dimensions": [8],
            "batch_norm": False,
        }
    else:
        hyperparameters = {"context_length": context_length}

    return {
        "model_name": model_name or f"test_{algorithm}",
        "algorithm": algorithm,
        "freq": freq,
        "prediction_length": prediction_length,
        "artifact_root": artifact_root,
        "dataset": {
            "series": generate_synthetic_series(
                num_series=num_series,
                length=length,
            )
        },
        "training": {
            "max_epochs": max_epochs,
            "batch_size": batch_size,
            "num_batches_per_epoch": num_batches_per_epoch,
            "accelerator": "cpu",
            "enable_progress_bar": False,
            "enable_model_summary": False,
            "logger": False,
        },
        "evaluation": {
            "enabled": True,
            "test_length": prediction_length,
            "num_samples": 20,
            "num_workers": 0,
            "quantiles": [0.1, 0.5, 0.9],
        },
        "hyperparameters": hyperparameters,
    }
