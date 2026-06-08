"""Request and result schemas for training GluonTS models."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AlgorithmName = Literal["deepar", "simple_feedforward"]


class TimeSeriesItem(BaseModel):
    """Single univariate time-series entry."""

    model_config = ConfigDict(extra="forbid")

    item_id: str | None = None
    start: str
    target: list[float]

    @field_validator("target")
    @classmethod
    def target_must_not_be_empty(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("target must contain at least one value")
        return value


class DatasetSpec(BaseModel):
    """Dataset payload accepted by the module."""

    model_config = ConfigDict(extra="forbid")

    series: list[TimeSeriesItem]

    @field_validator("series")
    @classmethod
    def series_must_not_be_empty(
        cls, value: list[TimeSeriesItem]
    ) -> list[TimeSeriesItem]:
        if not value:
            raise ValueError("dataset.series must contain at least one series")
        return value


class DatasetCsvSpec(BaseModel):
    """CSV dataset reference accepted by local APIs and binary wrappers."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["csv"]
    path: Path
    format: Literal["long"] = "long"
    item_id_column: str = "item_id"
    timestamp_column: str
    target_column: str


DatasetInput = DatasetSpec | DatasetCsvSpec


class DeepARHyperParameters(BaseModel):
    """Hyperparameters specific to GluonTS DeepAR."""

    model_config = ConfigDict(extra="forbid")

    context_length: int | None = Field(default=None, gt=0)
    num_layers: int = Field(default=2, gt=0)
    hidden_size: int = Field(default=40, gt=0)
    dropout_rate: float = Field(default=0.1, ge=0.0, lt=1.0)
    lr: float = Field(default=1e-3, gt=0.0)
    weight_decay: float = Field(default=1e-8, ge=0.0)
    num_parallel_samples: int = Field(default=100, gt=0)
    nonnegative_pred_samples: bool = False


class SimpleFeedForwardHyperParameters(BaseModel):
    """Hyperparameters specific to GluonTS SimpleFeedForward."""

    model_config = ConfigDict(extra="forbid")

    context_length: int | None = Field(default=None, gt=0)
    hidden_dimensions: list[int] = Field(default_factory=lambda: [40, 40])
    lr: float = Field(default=1e-3, gt=0.0)
    weight_decay: float = Field(default=1e-8, ge=0.0)
    batch_norm: bool = False

    @field_validator("hidden_dimensions")
    @classmethod
    def hidden_dimensions_must_be_positive(
        cls, value: list[int]
    ) -> list[int]:
        if not value:
            raise ValueError("hidden_dimensions must contain at least one layer")
        if any(item <= 0 for item in value):
            raise ValueError("hidden_dimensions must only contain positive integers")
        return value


class TrainingSettings(BaseModel):
    """General training settings shared by all estimators."""

    model_config = ConfigDict(extra="forbid")

    max_epochs: int = Field(default=5, gt=0)
    batch_size: int = Field(default=32, gt=0)
    num_batches_per_epoch: int = Field(default=50, gt=0)
    accelerator: str = "cpu"
    enable_progress_bar: bool = False
    enable_model_summary: bool = False
    logger: bool = False


class EvaluationSettings(BaseModel):
    """Optional holdout evaluation settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    test_length: int | None = Field(default=None, gt=0)
    num_samples: int = Field(default=100, gt=0)
    num_workers: int = Field(default=0, ge=0)
    quantiles: list[float] = Field(default_factory=lambda: [0.1, 0.5, 0.9])

    @field_validator("quantiles")
    @classmethod
    def quantiles_must_be_probabilities(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("quantiles must contain at least one value")
        if any(item <= 0.0 or item >= 1.0 for item in value):
            raise ValueError("quantiles must be between 0 and 1")
        return value


class TrainingRequest(BaseModel):
    """Top-level training request."""

    model_config = ConfigDict(extra="forbid")

    model_name: str
    algorithm: AlgorithmName
    freq: str
    prediction_length: int = Field(gt=0)
    dataset: DatasetInput
    artifact_root: Path = Path("artifacts/models")
    training: TrainingSettings = Field(default_factory=TrainingSettings)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_lengths(self) -> TrainingRequest:
        if isinstance(self.dataset, DatasetCsvSpec):
            return self

        holdout = self.evaluation.test_length or self.prediction_length

        if self.evaluation.enabled:
            for item in self.dataset.series:
                if len(item.target) <= holdout:
                    raise ValueError(
                        "each target length must be greater than evaluation "
                        "test_length"
                    )
        else:
            for item in self.dataset.series:
                if len(item.target) < self.prediction_length:
                    raise ValueError(
                        "each target length must be at least prediction_length"
                    )

        return self

    def model_hyperparameters(
        self,
    ) -> DeepARHyperParameters | SimpleFeedForwardHyperParameters:
        """Return validated hyperparameters for the selected algorithm."""
        if self.algorithm == "deepar":
            return DeepARHyperParameters.model_validate(self.hyperparameters)
        if self.algorithm == "simple_feedforward":
            return SimpleFeedForwardHyperParameters.model_validate(
                self.hyperparameters
            )
        raise ValueError(f"unsupported algorithm: {self.algorithm}")


class ModelMetadata(BaseModel):
    """Metadata written next to a saved model."""

    model_id: str
    model_name: str
    algorithm: AlgorithmName
    status: Literal["completed"]
    created_at: datetime
    model_path: str
    metadata_path: str
    request_path: str
    metrics_path: str | None = None


class TrainingResult(BaseModel):
    """Structured result returned by train_model."""

    model_id: str
    model_name: str
    algorithm: AlgorithmName
    status: Literal["completed"]
    model_path: str
    metadata_path: str
    metrics: dict[str, float] | None = None


class PredictionSettings(BaseModel):
    """Prediction-time settings."""

    model_config = ConfigDict(extra="forbid")

    num_samples: int = Field(default=100, gt=0)
    quantiles: list[float] = Field(default_factory=lambda: [0.1, 0.5, 0.9])

    @field_validator("quantiles")
    @classmethod
    def quantiles_must_be_probabilities(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("quantiles must contain at least one value")
        if any(item <= 0.0 or item >= 1.0 for item in value):
            raise ValueError("quantiles must be between 0 and 1")
        return value


class PredictionRequest(BaseModel):
    """Top-level prediction request."""

    model_config = ConfigDict(extra="forbid")

    dataset: DatasetInput
    model_id: str | None = None
    model_path: Path | None = None
    artifact_root: Path = Path("artifacts/models")
    freq: str | None = None
    prediction: PredictionSettings = Field(default_factory=PredictionSettings)

    @model_validator(mode="after")
    def require_model_reference(self) -> PredictionRequest:
        if self.model_id is None and self.model_path is None:
            raise ValueError("either model_id or model_path must be provided")
        return self


class ForecastResult(BaseModel):
    """Forecast payload for one time series."""

    item_id: str | None = None
    start_date: str
    mean: list[float]
    quantiles: dict[str, list[float]]


class PredictionResult(BaseModel):
    """Structured result returned by predict."""

    model_id: str | None = None
    model_path: str
    forecasts: list[ForecastResult]
