"""Dataset conversion helpers."""

from __future__ import annotations

import numpy as np

from gluonts.dataset.common import ListDataset

from traingluonts.schemas import DatasetSpec


def to_list_dataset(dataset: DatasetSpec, freq: str) -> ListDataset:
    """Convert a validated dataset payload into a GluonTS ListDataset."""
    return ListDataset(_entries(dataset), freq=freq)


def split_for_evaluation(
    dataset: DatasetSpec,
    freq: str,
    test_length: int,
) -> tuple[ListDataset, ListDataset]:
    """Build train and test datasets for holdout evaluation."""
    train_entries = []
    test_entries = []

    for entry in _entries(dataset):
        target = entry["target"]
        train_entries.append({**entry, "target": target[:-test_length]})
        test_entries.append(entry)

    return ListDataset(train_entries, freq=freq), ListDataset(test_entries, freq=freq)


def _entries(dataset: DatasetSpec) -> list[dict]:
    entries = []

    for index, item in enumerate(dataset.series):
        entry = {
            "item_id": item.item_id or f"series_{index}",
            "start": item.start,
            "target": np.asarray(item.target, dtype=np.float32),
        }
        entries.append(entry)

    return entries
