"""Prediction service used by the workflow-node ZeroMQ server."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from traingluonts.dataset import to_list_dataset
from traingluonts.errors import ModelRegistryError, PredictionRequestError
from traingluonts.registry import load_model
from traingluonts.workflow_node.payloads import (
    DEFAULT_START_TIME,
    data_rows_to_dataset,
    forecasts_to_output_rows,
    parse_request_text,
)


@dataclass(frozen=True)
class WorkflowNodeConfig:
    """Startup configuration for one workflow-node process."""

    model_path: Path
    target_name: str
    timestamp_name: str | None = None
    item_id_name: str | None = None
    freq: str | None = None
    start_time: str = DEFAULT_START_TIME
    num_samples: int = 100
    output_name: str = "predict_value"

    def __post_init__(self) -> None:
        if not self.target_name:
            raise PredictionRequestError("target_name is required")
        if not self.output_name:
            raise PredictionRequestError("output_name is required")
        if not self.start_time:
            raise PredictionRequestError("start_time is required")
        if self.num_samples <= 0:
            raise PredictionRequestError("num_samples must be positive")


class WorkflowPredictionService:
    """Handle workflow-node prediction requests with a preloaded predictor."""

    def __init__(
        self,
        *,
        predictor,
        config: WorkflowNodeConfig,
        freq: str,
        predictor_path: Path | None = None,
    ) -> None:
        self.predictor = predictor
        self.config = config
        self.freq = freq
        self.predictor_path = predictor_path

    @classmethod
    def from_config(cls, config: WorkflowNodeConfig) -> WorkflowPredictionService:
        """Load the configured model and return a ready prediction service."""
        predictor_path = resolve_predictor_path(config.model_path)
        freq = resolve_freq(config.freq, predictor_path)
        predictor = load_model(predictor_path)

        return cls(
            predictor=predictor,
            config=config,
            freq=freq,
            predictor_path=predictor_path,
        )

    def process_text(self, text: str) -> dict[str, Any]:
        """Process one raw JSON request string and return a response payload."""
        try:
            payload = parse_request_text(text)
            return self.process_payload(payload)
        except Exception as exc:
            return error_response(str(exc))

    def process_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process one parsed workflow-node request."""
        dataset = data_rows_to_dataset(
            payload,
            target_name=self.config.target_name,
            timestamp_name=self.config.timestamp_name,
            item_id_name=self.config.item_id_name,
            start_time=self.config.start_time,
        )
        list_dataset = to_list_dataset(dataset, self.freq)
        forecasts = list(
            self.predictor.predict(
                list_dataset,
                num_samples=self.config.num_samples,
            )
        )
        data = forecasts_to_output_rows(
            forecasts,
            output_name=self.config.output_name,
        )
        return success_response(data)


def resolve_predictor_path(model_path: str | Path) -> Path:
    """Resolve a platform model path to the serialized predictor directory."""
    path = Path(model_path).expanduser()

    if path.name == "predictor":
        predictor_path = path
    elif (path / "predictor").exists():
        predictor_path = path / "predictor"
    else:
        predictor_path = path

    if not predictor_path.exists():
        raise ModelRegistryError(f"model path does not exist: {predictor_path}")

    return predictor_path.resolve()


def resolve_freq(explicit_freq: str | None, predictor_path: Path) -> str:
    """Resolve the GluonTS frequency for workflow-node requests."""
    if explicit_freq:
        return explicit_freq

    request_path = find_training_request_path(predictor_path)
    if request_path is not None:
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        freq = payload.get("freq")
        if isinstance(freq, str) and freq:
            return freq

    raise PredictionRequestError(
        "freq is required when request.json cannot be found next to the model"
    )


def find_training_request_path(predictor_path: Path) -> Path | None:
    """Find the saved training request next to a serialized predictor."""
    candidates = []
    if predictor_path.name == "predictor":
        candidates.append(predictor_path.parent / "request.json")
    candidates.append(predictor_path / "request.json")
    candidates.append(predictor_path.parent / "request.json")

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved

    return None


def success_response(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a workflow-node success response."""
    return {
        "code": 200,
        "message": "success",
        "data": data,
    }


def error_response(message: str) -> dict[str, Any]:
    """Build a workflow-node error response."""
    return {
        "code": 500,
        "message": message,
        "data": {},
    }

