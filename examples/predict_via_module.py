"""
Train a tiny model and run prediction through the TrainGluonTS module interface.

Run from the project root:
    .\\.venv\\Scripts\\python.exe examples\\predict_via_module.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from traingluonts import predict, train_model
from traingluonts.testing import generate_training_request


def main() -> None:
    training_request = generate_training_request(
        algorithm="simple_feedforward",
        model_name="example_predictor",
        artifact_root="artifacts/models",
        num_series=2,
        length=40,
        prediction_length=5,
        context_length=10,
        max_epochs=1,
        num_batches_per_epoch=1,
        batch_size=2,
    )
    training_result = train_model(training_request)

    prediction_result = predict(
        {
            "model_id": training_result.model_id,
            "artifact_root": "artifacts/models",
            "dataset": training_request["dataset"],
            "prediction": {
                "num_samples": 20,
                "quantiles": [0.1, 0.5, 0.9],
            },
        }
    )

    first_forecast = prediction_result.forecasts[0]
    print("Prediction completed")
    print(f"  model_id:   {prediction_result.model_id}")
    print(f"  model_path: {prediction_result.model_path}")
    print(f"  item_id:    {first_forecast.item_id}")
    print(f"  start_date: {first_forecast.start_date}")
    print(f"  mean:       {first_forecast.mean}")
    print(f"  p50:        {first_forecast.quantiles['0.5']}")


if __name__ == "__main__":
    main()
