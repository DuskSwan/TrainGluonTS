"""Module-specific exceptions."""


class TrainGluonTSError(Exception):
    """Base exception for TrainGluonTS."""


class TrainingRequestError(TrainGluonTSError):
    """Raised when a training request is invalid."""


class ModelTrainingError(TrainGluonTSError):
    """Raised when model training or persistence fails."""


class PredictionRequestError(TrainGluonTSError):
    """Raised when a prediction request is invalid."""


class ModelPredictionError(TrainGluonTSError):
    """Raised when model loading or prediction fails."""


class ModelRegistryError(TrainGluonTSError):
    """Raised when local model registry operations fail."""
