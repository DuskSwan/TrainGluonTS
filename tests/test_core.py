from __future__ import annotations

import csv
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from traingluonts.dataset import read_csv_dataset, split_for_evaluation, to_list_dataset
from traingluonts.errors import (
    ModelRegistryError,
    PredictionRequestError,
    TrainingRequestError,
)
from traingluonts.estimators import create_estimator
from traingluonts.inference import predict, predict_with_model
from traingluonts.schemas import DatasetCsvSpec, PredictionRequest, TrainingRequest
from traingluonts.testing import generate_training_request
from traingluonts.trainer import train_model


class CoreTests(unittest.TestCase):
    def _write_csv_dataset(
        self,
        path: Path,
        *,
        num_series: int = 2,
        length: int = 30,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=["item_id", "timestamp", "target"],
            )
            writer.writeheader()
            for item_index in range(num_series):
                for day in range(length):
                    writer.writerow(
                        {
                            "item_id": f"series_{item_index}",
                            "timestamp": f"2024-01-{day + 1:02d}",
                            "target": float(10 + item_index + day),
                        }
                    )

    def test_dataset_conversion(self) -> None:
        request = TrainingRequest.model_validate(generate_training_request())

        dataset = to_list_dataset(request.dataset, request.freq)
        self.assertEqual(len(list(dataset)), len(request.dataset.series))

        train_ds, test_ds = split_for_evaluation(
            request.dataset,
            request.freq,
            request.prediction_length,
        )
        train_entries = list(train_ds)
        test_entries = list(test_ds)

        self.assertEqual(len(train_entries), len(test_entries))
        self.assertEqual(
            len(train_entries[0]["target"]),
            len(test_entries[0]["target"]) - request.prediction_length,
        )

    def test_csv_dataset_conversion(self) -> None:
        tmp_root = ROOT / "artifacts" / "test_runs"
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = tmp_root / f"csv_dataset_{uuid4().hex[:8]}"
        tmp_dir.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))

        csv_path = tmp_dir / "series.csv"
        self._write_csv_dataset(csv_path, num_series=2, length=5)

        dataset = read_csv_dataset(
            DatasetCsvSpec(
                type="csv",
                path=csv_path,
                timestamp_column="timestamp",
                target_column="target",
            )
        )

        self.assertEqual(len(dataset.series), 2)
        self.assertEqual(dataset.series[0].start, "2024-01-01")
        self.assertEqual(len(dataset.series[0].target), 5)

    def test_estimator_factory_supports_two_models(self) -> None:
        for algorithm in ["deepar", "simple_feedforward"]:
            with self.subTest(algorithm=algorithm):
                request = TrainingRequest.model_validate(
                    generate_training_request(algorithm=algorithm)
                )
                estimator = create_estimator(request, Path("artifacts/test_factory"))
                self.assertIsNotNone(estimator)

    def test_unknown_hyperparameter_is_rejected(self) -> None:
        request = generate_training_request(algorithm="deepar")
        request["hyperparameters"]["not_a_deepar_parameter"] = 1

        with self.assertRaises(TrainingRequestError):
            train_model(request)

    def test_prediction_request_requires_model_reference(self) -> None:
        request = generate_training_request()

        with self.assertRaises(PredictionRequestError):
            predict({"dataset": request["dataset"]})

    def test_prediction_missing_model_path_raises_module_error(self) -> None:
        request = generate_training_request()

        with self.assertRaises(ModelRegistryError):
            predict(
                {
                    "model_path": "artifacts/missing_model/predictor",
                    "freq": "D",
                    "dataset": request["dataset"],
                }
            )

    def test_tiny_training_run(self) -> None:
        tmp_root = ROOT / "artifacts" / "test_runs"
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = tmp_root / f"core_training_{uuid4().hex[:8]}"
        tmp_dir.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))

        request = generate_training_request(
            algorithm="simple_feedforward",
            artifact_root=str(tmp_dir),
            num_series=2,
            length=30,
            prediction_length=3,
            context_length=6,
            max_epochs=1,
            num_batches_per_epoch=1,
            batch_size=2,
        )
        result = train_model(request)

        self.assertEqual(result.algorithm, "simple_feedforward")
        self.assertTrue(Path(result.model_path).exists())
        self.assertTrue(Path(result.metadata_path).exists())
        self.assertIsNotNone(result.metrics)
        self.assertIn("RMSE", result.metrics or {})

    def test_train_from_csv_dataset(self) -> None:
        tmp_root = ROOT / "artifacts" / "test_runs"
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = tmp_root / f"core_training_csv_{uuid4().hex[:8]}"
        tmp_dir.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))

        csv_path = tmp_dir / "train.csv"
        self._write_csv_dataset(csv_path, num_series=2, length=30)

        request = generate_training_request(
            algorithm="simple_feedforward",
            artifact_root=str(tmp_dir),
            num_series=2,
            length=30,
            prediction_length=3,
            context_length=6,
            max_epochs=1,
            num_batches_per_epoch=1,
            batch_size=2,
        )
        request["dataset"] = {
            "type": "csv",
            "path": str(csv_path),
            "timestamp_column": "timestamp",
            "target_column": "target",
        }

        result = train_model(request)

        self.assertEqual(result.algorithm, "simple_feedforward")
        self.assertTrue(Path(result.model_path).exists())

    def test_train_then_predict_by_model_id(self) -> None:
        tmp_root = ROOT / "artifacts" / "test_runs"
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = tmp_root / f"core_predict_{uuid4().hex[:8]}"
        tmp_dir.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))

        request = generate_training_request(
            algorithm="simple_feedforward",
            artifact_root=str(tmp_dir),
            num_series=2,
            length=30,
            prediction_length=3,
            context_length=6,
            max_epochs=1,
            num_batches_per_epoch=1,
            batch_size=2,
        )
        training_result = train_model(request)

        prediction_result = predict(
            {
                "model_id": training_result.model_id,
                "artifact_root": str(tmp_dir),
                "dataset": request["dataset"],
                "prediction": {
                    "num_samples": 20,
                    "quantiles": [0.1, 0.5, 0.9],
                },
            }
        )

        self.assertEqual(prediction_result.model_id, training_result.model_id)
        self.assertTrue(Path(prediction_result.model_path).exists())
        self.assertEqual(len(prediction_result.forecasts), 2)
        self.assertEqual(len(prediction_result.forecasts[0].mean), 3)
        self.assertIn("0.5", prediction_result.forecasts[0].quantiles)

    def test_predict_from_csv_dataset(self) -> None:
        tmp_root = ROOT / "artifacts" / "test_runs"
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = tmp_root / f"core_predict_csv_{uuid4().hex[:8]}"
        tmp_dir.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))

        csv_path = tmp_dir / "predict.csv"
        self._write_csv_dataset(csv_path, num_series=2, length=30)

        request = generate_training_request(
            algorithm="simple_feedforward",
            artifact_root=str(tmp_dir),
            num_series=2,
            length=30,
            prediction_length=3,
            context_length=6,
            max_epochs=1,
            num_batches_per_epoch=1,
            batch_size=2,
        )
        training_result = train_model(request)

        prediction_result = predict(
            {
                "model_id": training_result.model_id,
                "artifact_root": str(tmp_dir),
                "dataset": {
                    "type": "csv",
                    "path": str(csv_path),
                    "timestamp_column": "timestamp",
                    "target_column": "target",
                },
                "prediction": {
                    "num_samples": 20,
                    "quantiles": [0.5],
                },
            }
        )

        self.assertEqual(len(prediction_result.forecasts), 2)
        self.assertIn("0.5", prediction_result.forecasts[0].quantiles)

    def test_predict_by_model_path(self) -> None:
        tmp_root = ROOT / "artifacts" / "test_runs"
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = tmp_root / f"core_predict_path_{uuid4().hex[:8]}"
        tmp_dir.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))

        request = generate_training_request(
            algorithm="simple_feedforward",
            artifact_root=str(tmp_dir),
            num_series=1,
            length=30,
            prediction_length=3,
            context_length=6,
            max_epochs=1,
            num_batches_per_epoch=1,
            batch_size=1,
        )
        training_result = train_model(request)

        prediction_request = PredictionRequest.model_validate(
            {
                "model_path": training_result.model_path,
                "dataset": request["dataset"],
            }
        )
        prediction_result = predict(prediction_request)

        self.assertIsNone(prediction_result.model_id)
        self.assertEqual(len(prediction_result.forecasts), 1)
        self.assertEqual(len(prediction_result.forecasts[0].mean), 3)

        helper_result = predict_with_model(
            training_result.model_path,
            request["dataset"],
            freq="D",
            num_samples=20,
            quantiles=[0.5],
        )
        self.assertEqual(len(helper_result.forecasts), 1)
        self.assertIn("0.5", helper_result.forecasts[0].quantiles)


if __name__ == "__main__":
    unittest.main()
