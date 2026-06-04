"""
Train a GluonTS model through the TrainGluonTS module interface.

Run from the project root:
    .\\.venv\\Scripts\\python.exe examples\\train_via_module.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from traingluonts import train_model
from traingluonts.testing import generate_training_request


def main() -> None:
    request = generate_training_request(
        algorithm="deepar",
        model_name="example_deepar",
        artifact_root="artifacts/models",
    )
    result = train_model(request)

    print("Training completed")
    print(f"  model_id:      {result.model_id}")
    print(f"  algorithm:     {result.algorithm}")
    print(f"  model_path:    {result.model_path}")
    print(f"  metadata_path: {result.metadata_path}")
    print(f"  metrics:       {result.metrics}")


if __name__ == "__main__":
    main()
