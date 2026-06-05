"""JSON IO helpers for the TrainGluonTS CLI."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, TextIO


class CliInputError(Exception):
    """Raised when CLI input files or JSON payloads are invalid."""


def read_request_json(path: str | Path) -> dict[str, Any]:
    """Read a request JSON file and normalize relative filesystem paths."""
    input_path = Path(path).expanduser().resolve()

    try:
        raw = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliInputError(f"cannot read input JSON: {input_path}: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        message = (
            f"invalid JSON in {input_path}: {exc.msg} "
            f"at line {exc.lineno} column {exc.colno}"
        )
        raise CliInputError(message) from exc

    if not isinstance(payload, dict):
        raise CliInputError("input JSON must be a JSON object")

    return normalize_request_paths(payload, input_path.parent)


def normalize_request_paths(
    payload: dict[str, Any],
    base_dir: Path,
) -> dict[str, Any]:
    """Resolve relative request paths from the directory containing input JSON."""
    normalized = copy.deepcopy(payload)

    _resolve_path_field(normalized, "artifact_root", base_dir)
    _resolve_path_field(normalized, "model_path", base_dir)

    dataset = normalized.get("dataset")
    if isinstance(dataset, dict) and dataset.get("type") == "csv":
        _resolve_path_field(dataset, "path", base_dir)

    return normalized


def write_response(
    payload: dict[str, Any],
    output: str | Path | None = None,
    *,
    pretty: bool = False,
    stream: TextIO | None = None,
) -> None:
    """Write a CLI response payload to stdout or a JSON file."""
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2 if pretty else None,
        default=str,
    )

    if output is None:
        print(text, file=stream or sys.stdout)
        return

    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")


def _resolve_path_field(
    container: dict[str, Any],
    field: str,
    base_dir: Path,
) -> None:
    value = container.get(field)
    if not isinstance(value, str) or value == "":
        return

    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path

    container[field] = str(path.resolve())

