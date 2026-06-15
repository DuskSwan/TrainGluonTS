from __future__ import annotations

import json
import sys
import threading
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import zmq

from traingluonts.errors import ModelRegistryError, PredictionRequestError
from traingluonts.workflow_node.main import config_from_args, serve_forever
from traingluonts.workflow_node.payloads import (
    DEFAULT_START_TIME,
    WorkflowPayloadError,
    data_rows_to_dataset,
    forecasts_to_output_rows,
    parse_request_text,
)
from traingluonts.workflow_node.service import (
    WorkflowNodeConfig,
    WorkflowPredictionService,
    resolve_freq,
    resolve_predictor_path,
)


class WorkflowNodeTests(unittest.TestCase):
    def test_parse_request_text_requires_json_object(self) -> None:
        with self.assertRaises(WorkflowPayloadError):
            parse_request_text("[1, 2, 3]")

        with self.assertRaises(WorkflowPayloadError):
            parse_request_text("{")

    def test_data_rows_without_timestamp_use_default_start(self) -> None:
        dataset = data_rows_to_dataset(
            {
                "data": [
                    {"value": "1.5"},
                    {"value": 2},
                ]
            },
            target_name="value",
        )

        self.assertEqual(len(dataset.series), 1)
        self.assertEqual(dataset.series[0].item_id, "series_0")
        self.assertEqual(dataset.series[0].start, DEFAULT_START_TIME)
        self.assertEqual(dataset.series[0].target, [1.5, 2.0])

    def test_data_rows_group_by_item_id(self) -> None:
        dataset = data_rows_to_dataset(
            {
                "data": [
                    {"sensor": "A", "time": "2026-01-01 00:00:00", "value": 1},
                    {"sensor": "B", "time": "2026-01-01 00:00:00", "value": 10},
                    {"sensor": "A", "time": "2026-01-01 00:00:00.030", "value": 2},
                    {"sensor": "B", "time": "2026-01-01 00:00:00.030", "value": 11},
                ]
            },
            target_name="value",
            timestamp_name="time",
            item_id_name="sensor",
        )

        self.assertEqual([item.item_id for item in dataset.series], ["A", "B"])
        self.assertEqual(dataset.series[0].start, "2026-01-01 00:00:00")
        self.assertEqual(dataset.series[0].target, [1.0, 2.0])
        self.assertEqual(dataset.series[1].target, [10.0, 11.0])

    def test_data_rows_reject_invalid_payloads(self) -> None:
        cases = [
            ({}, "data must be a non-empty array"),
            ({"data": []}, "data must be a non-empty array"),
            ({"data": [1]}, "data row 0 must be a JSON object"),
            ({"data": [{"other": 1}]}, "missing target field: value"),
            ({"data": [{"value": "bad"}]}, "invalid target value"),
            ({"data": [{"value": 1, "sensor": ""}]}, "empty item id field"),
        ]

        for payload, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(WorkflowPayloadError, message):
                    data_rows_to_dataset(
                        payload,
                        target_name="value",
                        item_id_name="sensor" if "item id" in message else None,
                    )

    def test_forecasts_to_output_rows_only_returns_mean_values(self) -> None:
        rows = forecasts_to_output_rows(
            [
                FakeForecast("series_0", [1.25, 2.5]),
            ],
            output_name="y_hat",
        )

        self.assertEqual(
            rows,
            [
                {"item_id": "series_0", "step": 1, "y_hat": 1.25},
                {"item_id": "series_0", "step": 2, "y_hat": 2.5},
            ],
        )
        self.assertNotIn("quantiles", rows[0])
        self.assertNotIn("model_path", rows[0])

    def test_service_processes_payload_with_preloaded_predictor(self) -> None:
        predictor = FakePredictor()
        service = WorkflowPredictionService(
            predictor=predictor,
            config=WorkflowNodeConfig(
                model_path=Path("unused"),
                target_name="value",
                freq="30ms",
                num_samples=7,
                output_name="predict_value",
            ),
            freq="30ms",
        )

        response = service.process_payload(
            {
                "data": [
                    {"value": 3},
                    {"value": 4},
                ]
            }
        )

        self.assertEqual(response["code"], 200)
        self.assertEqual(response["type"], "timeseries")
        self.assertEqual(
            response["data"],
            [
                {"item_id": "series_0", "step": 1, "predict_value": 5.0},
                {"item_id": "series_0", "step": 2, "predict_value": 6.0},
            ],
        )
        self.assertEqual(predictor.num_samples, 7)
        self.assertEqual(predictor.freq_entry_count, 1)

    def test_service_returns_error_response_for_bad_request(self) -> None:
        service = WorkflowPredictionService(
            predictor=FakePredictor(),
            config=WorkflowNodeConfig(
                model_path=Path("unused"),
                target_name="value",
                freq="30ms",
            ),
            freq="30ms",
        )

        response = service.process_text('{"data": [{"other": 1}]}')

        self.assertEqual(response["code"], 500)
        self.assertEqual(response["type"], "timeseries")
        self.assertIn("missing target field: value", response["message"])

    def test_config_rejects_non_req_protocol(self) -> None:
        args = Namespace(
            zmq_protocol="DEALER",
            model_path="model",
            target_name="value",
            timestamp_name=None,
            item_id_name=None,
            freq="30ms",
            start_time=DEFAULT_START_TIME,
            num_samples=100,
            output_name="predict_value",
        )

        with self.assertRaisesRegex(ValueError, "REQ"):
            config_from_args(args)

    def test_config_rejects_invalid_num_samples(self) -> None:
        with self.assertRaisesRegex(PredictionRequestError, "num_samples"):
            WorkflowNodeConfig(
                model_path=Path("unused"),
                target_name="value",
                num_samples=0,
            )

    def test_resolve_predictor_path_accepts_model_root_or_predictor_dir(self) -> None:
        root = ROOT / "artifacts" / "test_runs" / "workflow_node_paths"
        predictor_dir = root / "model_001" / "predictor"
        predictor_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: _remove_tree(root))

        self.assertEqual(resolve_predictor_path(predictor_dir), predictor_dir.resolve())
        self.assertEqual(
            resolve_predictor_path(predictor_dir.parent),
            predictor_dir.resolve(),
        )

        with self.assertRaises(ModelRegistryError):
            resolve_predictor_path(root / "missing")

    def test_resolve_freq_prefers_explicit_then_request_json(self) -> None:
        root = ROOT / "artifacts" / "test_runs" / "workflow_node_freq"
        predictor_dir = root / "model_001" / "predictor"
        predictor_dir.mkdir(parents=True, exist_ok=True)
        (predictor_dir.parent / "request.json").write_text(
            json.dumps({"freq": "50ms"}),
            encoding="utf-8",
        )
        self.addCleanup(lambda: _remove_tree(root))

        self.assertEqual(resolve_freq("30ms", predictor_dir), "30ms")
        self.assertEqual(resolve_freq(None, predictor_dir), "50ms")

        (predictor_dir.parent / "request.json").unlink()
        with self.assertRaises(PredictionRequestError):
            resolve_freq(None, predictor_dir)

    def test_zmq_req_rep_server_handles_success_and_error(self) -> None:
        endpoint = "inproc://workflow-node-test"
        context = zmq.Context()
        service = WorkflowPredictionService(
            predictor=FakePredictor(),
            config=WorkflowNodeConfig(
                model_path=Path("unused"),
                target_name="value",
                freq="30ms",
            ),
            freq="30ms",
        )
        server = threading.Thread(
            target=serve_forever,
            args=(endpoint, service),
            kwargs={"max_requests": 2, "context": context},
            daemon=True,
        )
        server.start()

        client = context.socket(zmq.REQ)
        client.setsockopt(zmq.RCVTIMEO, 3000)
        client.connect(endpoint)
        try:
            client.send_string(json.dumps({"data": [{"value": 1}, {"value": 2}]}))
            success = json.loads(client.recv_string())
            client.send_string(json.dumps({"data": [{"other": 1}]}))
            error = json.loads(client.recv_string())
        finally:
            client.close(linger=0)
            context.term()
            server.join(timeout=3)

        self.assertFalse(server.is_alive())
        self.assertEqual(success["code"], 200)
        self.assertEqual(success["type"], "timeseries")
        self.assertEqual(success["data"][0]["predict_value"], 3.0)
        self.assertEqual(error["code"], 500)
        self.assertEqual(error["type"], "timeseries")


class FakeForecast:
    def __init__(self, item_id: str, mean: list[float]) -> None:
        self.item_id = item_id
        self.mean = mean


class FakePredictor:
    def __init__(self) -> None:
        self.num_samples: int | None = None
        self.freq_entry_count = 0

    def predict(self, dataset, *, num_samples: int):
        self.num_samples = num_samples
        entries = list(dataset)
        self.freq_entry_count = len(entries)

        forecasts = []
        for entry in entries:
            target = entry["target"]
            last_value = float(target[-1])
            forecasts.append(
                FakeForecast(
                    entry.get("item_id"),
                    [last_value + 1.0, last_value + 2.0],
                )
            )

        return forecasts


def _remove_tree(path: Path) -> None:
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file():
            child.unlink()
        else:
            child.rmdir()
    path.rmdir()


if __name__ == "__main__":
    unittest.main()
