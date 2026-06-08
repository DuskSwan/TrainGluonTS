from __future__ import annotations

import csv
import asyncio
import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from traingluonts.api.app import create_app
from traingluonts.api.settings import ApiSettings
from traingluonts.testing import generate_training_request


class AsgiResponse:
    def __init__(self, status_code: int, body: bytes) -> None:
        self.status_code = status_code
        self.text = body.decode("utf-8")

    def json(self) -> dict:
        return json.loads(self.text)


class AsgiClient:
    def __init__(self, app) -> None:
        self.app = app

    def get(self, path: str) -> AsgiResponse:
        return self.request("GET", path)

    def post(self, path: str, *, json: dict) -> AsgiResponse:
        body = json_module.dumps(json).encode("utf-8")
        return self.request("POST", path, body=body)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes = b"",
    ) -> AsgiResponse:
        return asyncio.run(self._request(method, path, body))

    async def _request(self, method: str, path: str, body: bytes) -> AsgiResponse:
        messages = []
        request_sent = False

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [
                (b"content-type", b"application/json"),
                (b"server", b"testserver"),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }

        async def receive() -> dict:
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }
            return {"type": "http.disconnect"}

        async def send(message: dict) -> None:
            messages.append(message)

        await self.app(scope, receive, send)

        status_code = 500
        response_body = bytearray()
        for message in messages:
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                response_body.extend(message.get("body", b""))

        return AsgiResponse(status_code, bytes(response_body))


json_module = json


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = ROOT / "artifacts" / "test_runs" / f"api_{uuid4().hex[:8]}"
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.tmp_root, ignore_errors=True))

        self.data_root = self.tmp_root / "data"
        self.artifact_root = self.tmp_root / "models"
        self.csv_path = self.data_root / "series.csv"
        self._write_csv_dataset(self.csv_path)

        settings = ApiSettings(
            artifact_root=self.artifact_root,
            data_root=self.data_root,
            cors_origins=[],
        )
        self.client = AsgiClient(create_app(settings))

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

    def _training_payload(self) -> dict:
        payload = generate_training_request(
            algorithm="simple_feedforward",
            artifact_root=str(self.artifact_root),
            num_series=2,
            length=30,
            prediction_length=3,
            context_length=6,
            max_epochs=1,
            num_batches_per_epoch=1,
            batch_size=2,
        )
        payload["dataset"] = {
            "type": "csv",
            "path": "series.csv",
            "timestamp_column": "timestamp",
            "target_column": "target",
        }
        return payload

    def _train_model_via_api(self) -> dict:
        response = self.client.post("/api/v1/train", json=self._training_payload())
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["ok"])
        return payload["result"]

    def test_health_and_version(self) -> None:
        health = self.client.get("/api/v1/health")
        version = self.client.get("/api/v1/version")

        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["ok"])
        self.assertEqual(health.json()["result"]["status"], "healthy")
        self.assertEqual(version.status_code, 200)
        self.assertEqual(version.json()["result"]["version"], "0.1.0")

    def test_sync_train_predict_and_load_check(self) -> None:
        training_result = self._train_model_via_api()
        self.assertTrue(Path(training_result["model_path"]).exists())

        load_check = self.client.get(
            f"/api/v1/models/{training_result['model_id']}/load-check"
        )
        self.assertEqual(load_check.status_code, 200, load_check.text)
        self.assertTrue(load_check.json()["result"]["loadable"])

        prediction = self.client.post(
            "/api/v1/predict",
            json={
                "model_id": training_result["model_id"],
                "artifact_root": str(self.artifact_root),
                "dataset": {
                    "type": "csv",
                    "path": "series.csv",
                    "timestamp_column": "timestamp",
                    "target_column": "target",
                },
                "prediction": {
                    "num_samples": 20,
                    "quantiles": [0.5],
                },
            },
        )
        self.assertEqual(prediction.status_code, 200, prediction.text)
        prediction_payload = prediction.json()
        self.assertTrue(prediction_payload["ok"])
        self.assertEqual(len(prediction_payload["result"]["forecasts"]), 2)
        self.assertIn(
            "0.5",
            prediction_payload["result"]["forecasts"][0]["quantiles"],
        )

    def test_async_training_job(self) -> None:
        response = self.client.post(
            "/api/v1/train/jobs",
            json={"request": self._training_payload()},
        )
        self.assertEqual(response.status_code, 200, response.text)
        job = response.json()["result"]
        self.assertIn(job["status"], {"queued", "running", "completed"})

        status_response = self.client.get(f"/api/v1/train/jobs/{job['job_id']}")
        self.assertEqual(status_response.status_code, 200, status_response.text)
        status = status_response.json()["result"]
        self.assertEqual(status["status"], "completed")
        self.assertIsNotNone(status["result"])

    def test_predict_with_model(self) -> None:
        training_result = self._train_model_via_api()

        response = self.client.post(
            "/api/v1/predict-with-model",
            json={
                "model_path": training_result["model_path"],
                "freq": "D",
                "dataset": {
                    "type": "csv",
                    "path": "series.csv",
                    "timestamp_column": "timestamp",
                    "target_column": "target",
                },
                "prediction": {
                    "num_samples": 20,
                    "quantiles": [0.5],
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(len(response.json()["result"]["forecasts"]), 2)

    def test_missing_csv_returns_unified_error(self) -> None:
        request = self._training_payload()
        request["dataset"]["path"] = "missing.csv"

        response = self.client.post("/api/v1/train", json=request)
        payload = response.json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["type"], "TrainingRequestError")

    def test_unknown_job_returns_unified_error(self) -> None:
        response = self.client.get("/api/v1/train/jobs/missing")
        payload = response.json()

        self.assertEqual(response.status_code, 404)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["type"], "JobNotFound")

    def test_empty_model_load_check_returns_unified_error(self) -> None:
        response = self.client.post("/api/v1/models/load-check", json={})
        payload = response.json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["type"], "PredictionRequestError")


if __name__ == "__main__":
    unittest.main()
