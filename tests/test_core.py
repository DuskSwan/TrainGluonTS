from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from traingluonts.dataset import split_for_evaluation, to_list_dataset
from traingluonts.errors import TrainingRequestError
from traingluonts.estimators import create_estimator
from traingluonts.schemas import TrainingRequest
from traingluonts.testing import generate_training_request
from traingluonts.trainer import train_model


class CoreTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
