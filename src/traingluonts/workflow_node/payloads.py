"""Payload conversion helpers for workflow-node inference."""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np

from traingluonts.schemas import DatasetSpec


DEFAULT_START_TIME = "1970-01-01 00:00:00"


class WorkflowPayloadError(ValueError):
    """Raised when a workflow-node request payload is invalid."""


def parse_request_text(text: str) -> dict[str, Any]:
    """Parse one workflow-node request JSON string."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        message = (
            f"invalid JSON: {exc.msg} at line {exc.lineno} "
            f"column {exc.colno}"
        )
        raise WorkflowPayloadError(message) from exc

    if not isinstance(payload, dict):
        raise WorkflowPayloadError("request must be a JSON object")

    return payload


def data_rows_to_dataset(
    payload: dict[str, Any],
    *,
    target_name: str,
    timestamp_name: str | None = None,
    item_id_name: str | None = None,
    start_time: str = DEFAULT_START_TIME,
) -> DatasetSpec:
    """Convert workflow ``data`` rows to a GluonTS-compatible dataset."""
    rows = _extract_rows(payload)
    groups: dict[str, dict[str, Any]] = {}

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise WorkflowPayloadError(f"data row {index} must be a JSON object")

        item_id = _row_item_id(row, item_id_name)
        target = _row_target(row, target_name)

        group = groups.get(item_id)
        if group is None:
            group = {
                "item_id": item_id,
                "start": _row_start(row, timestamp_name, start_time),
                "target": [],
            }
            groups[item_id] = group

        group["target"].append(target)

    return DatasetSpec.model_validate({"series": list(groups.values())})


def forecasts_to_output_rows(forecasts, *, output_name: str) -> list[dict[str, Any]]:
    """Convert GluonTS forecast means to workflow response rows."""
    output_rows: list[dict[str, Any]] = []

    for forecast in forecasts:
        item_id = getattr(forecast, "item_id", None)
        mean_values = np.asarray(getattr(forecast, "mean")).reshape(-1).tolist()

        for step, value in enumerate(mean_values, start=1):
            row: dict[str, Any] = {
                "step": step,
                output_name: float(value),
            }
            if item_id is not None:
                row = {"item_id": str(item_id), **row}
            output_rows.append(row)

    return output_rows


def _extract_rows(payload: dict[str, Any]) -> list[Any]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise WorkflowPayloadError("data must be a non-empty array")
    if not data:
        raise WorkflowPayloadError("data must be a non-empty array")
    return data


def _row_item_id(row: dict[str, Any], item_id_name: str | None) -> str:
    if item_id_name is None:
        return "series_0"

    if item_id_name not in row:
        raise WorkflowPayloadError(f"missing item id field: {item_id_name}")

    value = row[item_id_name]
    if value is None or value == "":
        raise WorkflowPayloadError(f"empty item id field: {item_id_name}")

    return str(value)


def _row_start(
    row: dict[str, Any],
    timestamp_name: str | None,
    start_time: str,
) -> str:
    if timestamp_name is None:
        return start_time

    if timestamp_name not in row:
        raise WorkflowPayloadError(f"missing timestamp field: {timestamp_name}")

    value = row[timestamp_name]
    if value is None or value == "":
        raise WorkflowPayloadError(f"empty timestamp field: {timestamp_name}")

    return str(value)


def _row_target(row: dict[str, Any], target_name: str) -> float:
    if target_name not in row:
        raise WorkflowPayloadError(f"missing target field: {target_name}")

    try:
        value = float(row[target_name])
    except (TypeError, ValueError) as exc:
        raise WorkflowPayloadError(
            f"invalid target value for field {target_name}: {row[target_name]!r}"
        ) from exc

    if not math.isfinite(value):
        raise WorkflowPayloadError(
            f"invalid target value for field {target_name}: {row[target_name]!r}"
        )

    return value

