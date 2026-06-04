"""Public package interface for TrainGluonTS."""

from traingluonts.registry import load_model
from traingluonts.schemas import TrainingRequest, TrainingResult
from traingluonts.trainer import train_model

__all__ = [
    "TrainingRequest",
    "TrainingResult",
    "load_model",
    "train_model",
]
