"""Local model registry helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from gluonts.torch.model.predictor import PyTorchPredictor

from traingluonts.errors import ModelRegistryError
from traingluonts.schemas import ModelMetadata, TrainingRequest


def create_model_id(now: datetime | None = None) -> str:
    """Create a stable, sortable model id."""
    current = now or datetime.now(timezone.utc)
    stamp = current.strftime("%Y%m%d_%H%M%S")
    return f"model_{stamp}_{uuid4().hex[:6]}"


def prepare_model_dir(artifact_root: Path, model_id: str) -> Path:
    """Create and return the directory for one model."""
    root = artifact_root.resolve()
    model_dir = (root / model_id).resolve()

    if root not in model_dir.parents and model_dir != root:
        raise ModelRegistryError("model directory is outside artifact root")

    model_dir.mkdir(parents=True, exist_ok=False)
    return model_dir


def write_json(path: Path, payload: object) -> None:
    """Write JSON with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def build_metadata(
    request: TrainingRequest,
    model_id: str,
    model_dir: Path,
    metrics_path: Path | None,
) -> ModelMetadata:
    predictor_dir = model_dir / "predictor"
    metadata_path = model_dir / "metadata.json"
    request_path = model_dir / "request.json"

    return ModelMetadata(
        model_id=model_id,
        model_name=request.model_name,
        algorithm=request.algorithm,
        status="completed",
        created_at=datetime.now(timezone.utc),
        model_path=str(predictor_dir),
        metadata_path=str(metadata_path),
        request_path=str(request_path),
        metrics_path=str(metrics_path) if metrics_path is not None else None,
    )


def load_model(model_path_or_id: str | Path, artifact_root: Path | None = None):
    """Load a serialized GluonTS PyTorch predictor.

    Pass either a predictor directory path or a model id plus artifact_root.
    """
    value = Path(model_path_or_id)

    if artifact_root is not None and not value.exists():
        value = artifact_root / value / "predictor"

    if not value.exists():
        raise ModelRegistryError(f"model path does not exist: {value}")

    return PyTorchPredictor.deserialize(value)
