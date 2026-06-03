"""
Minimal GluonTS training example using the Torch backend.

Run from the project root:
    .\\.venv\\Scripts\\python.exe examples\\basic_gluonts_usage.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from gluonts.dataset.common import ListDataset
from gluonts.evaluation import Evaluator, make_evaluation_predictions
from gluonts.torch.model.deepar import DeepAREstimator


FREQ = "D"
PREDICTION_LENGTH = 14
TRAIN_LENGTH = 120
NUM_SERIES = 8


def build_series() -> list[dict]:
    """Create a tiny synthetic daily dataset with trend and seasonality."""
    rng = np.random.default_rng(seed=7)
    series: list[dict] = []

    for item_id in range(NUM_SERIES):
        time = np.arange(TRAIN_LENGTH + PREDICTION_LENGTH)
        weekly_pattern = 4.0 * np.sin(2 * np.pi * time / 7)
        trend = 0.08 * time
        level = 20 + item_id * 3
        noise = rng.normal(loc=0.0, scale=0.8, size=time.shape)
        target = level + trend + weekly_pattern + noise

        series.append(
            {
                "item_id": f"series_{item_id}",
                "start": "2024-01-01",
                "target": target.astype(np.float32),
            }
        )

    return series


def main() -> None:
    all_series = build_series()

    train_ds = ListDataset(
        [
            {
                **entry,
                "target": entry["target"][:-PREDICTION_LENGTH],
            }
            for entry in all_series
        ],
        freq=FREQ,
    )
    test_ds = ListDataset(all_series, freq=FREQ)

    estimator = DeepAREstimator(
        freq=FREQ,
        prediction_length=PREDICTION_LENGTH,
        context_length=28,
        num_layers=2,
        hidden_size=32,
        batch_size=16,
        num_batches_per_epoch=5,
        trainer_kwargs={
            "max_epochs": 1,
            "accelerator": "cpu",
            "default_root_dir": "artifacts/gluonts_demo",
            "enable_model_summary": False,
            "enable_progress_bar": False,
            "logger": False,
        },
    )

    predictor = estimator.train(train_ds)

    forecast_it, ts_it = make_evaluation_predictions(
        dataset=test_ds,
        predictor=predictor,
        num_samples=100,
    )
    forecasts = list(forecast_it)
    time_series = list(ts_it)

    evaluator = Evaluator(quantiles=[0.1, 0.5, 0.9])
    aggregate_metrics, _ = evaluator(time_series, forecasts)

    first_forecast = forecasts[0]
    print("First series forecast:")
    print(f"  start date: {first_forecast.start_date}")
    print(f"  mean:       {np.round(first_forecast.mean, 2).tolist()}")
    print(f"  p10:        {np.round(first_forecast.quantile(0.1), 2).tolist()}")
    print(f"  p50:        {np.round(first_forecast.quantile(0.5), 2).tolist()}")
    print(f"  p90:        {np.round(first_forecast.quantile(0.9), 2).tolist()}")

    print("\nAggregate metrics:")
    for metric_name in ["MASE", "MAPE", "RMSE", "mean_wQuantileLoss"]:
        print(f"  {metric_name}: {aggregate_metrics[metric_name]:.4f}")

    model_dir = Path("artifacts") / "gluonts_demo" / "deepar_predictor"
    model_dir.mkdir(parents=True, exist_ok=True)
    predictor.serialize(model_dir)
    print(f"\nSaved predictor to: {model_dir}")


if __name__ == "__main__":
    main()
