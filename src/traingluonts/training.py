"""Low-level GluonTS training helpers."""

from __future__ import annotations

from typing import Any

import lightning.pytorch as pl

from gluonts.dataset.common import Dataset
from gluonts.env import env
from gluonts.itertools import Cached
from gluonts.torch.model.estimator import TrainOutput


def train_estimator_without_checkpoint_pruning(
    estimator: Any,
    training_data: Dataset,
    validation_data: Dataset | None = None,
    cache_data: bool = False,
) -> TrainOutput:
    """Train a GluonTS Torch estimator without deleting old checkpoints.

    GluonTS injects a ModelCheckpoint callback by default. On Windows, pruning
    older checkpoint files can fail with PermissionError. This helper keeps all
    checkpoints and loads the last trained in-memory module into the predictor.
    """
    transformation = estimator.create_transformation()

    with env._let(max_idle_transforms=max(len(training_data), 100)):
        transformed_training_data = transformation.apply(
            training_data,
            is_train=True,
        )
        if cache_data:
            transformed_training_data = Cached(transformed_training_data)

        training_network = estimator.create_lightning_module()
        training_data_loader = estimator.create_training_data_loader(
            transformed_training_data,
            training_network,
        )

    validation_data_loader = None
    if validation_data is not None:
        with env._let(max_idle_transforms=max(len(validation_data), 100)):
            transformed_validation_data = transformation.apply(
                validation_data,
                is_train=True,
            )
            if cache_data:
                transformed_validation_data = Cached(transformed_validation_data)

            validation_data_loader = estimator.create_validation_data_loader(
                transformed_validation_data,
                training_network,
            )

    trainer = pl.Trainer(
        **{
            "accelerator": "auto",
            "callbacks": [
                pl.callbacks.ModelCheckpoint(
                    monitor="train_loss" if validation_data is None else "val_loss",
                    mode="min",
                    verbose=True,
                    save_top_k=-1,
                )
            ],
            **estimator.trainer_kwargs,
        }
    )
    trainer.fit(
        model=training_network,
        train_dataloaders=training_data_loader,
        val_dataloaders=validation_data_loader,
    )

    return TrainOutput(
        transformation=transformation,
        trained_net=training_network,
        trainer=trainer,
        predictor=estimator.create_predictor(transformation, training_network),
    )
