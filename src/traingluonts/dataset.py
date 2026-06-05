"""Dataset conversion helpers."""

from __future__ import annotations

import csv
from collections import defaultdict

import numpy as np

from gluonts.dataset.common import ListDataset

from traingluonts.schemas import DatasetCsvSpec, DatasetInput, DatasetSpec


def resolve_dataset(dataset: DatasetInput) -> DatasetSpec:
    """Resolve an inline or CSV-backed dataset into DatasetSpec."""
    if isinstance(dataset, DatasetSpec):
        return dataset
    return read_csv_dataset(dataset)


def to_list_dataset(dataset: DatasetInput, freq: str) -> ListDataset:
    """Convert a validated dataset payload into a GluonTS ListDataset."""
    return ListDataset(_entries(resolve_dataset(dataset)), freq=freq)


def split_for_evaluation(
    dataset: DatasetInput,
    freq: str,
    test_length: int,
) -> tuple[ListDataset, ListDataset]:
    """Build train and test datasets for holdout evaluation."""
    train_entries = []
    test_entries = []

    for entry in _entries(resolve_dataset(dataset)):
        target = entry["target"]
        train_entries.append({**entry, "target": target[:-test_length]})
        test_entries.append(entry)

    return ListDataset(train_entries, freq=freq), ListDataset(test_entries, freq=freq)


def read_csv_dataset(spec: DatasetCsvSpec) -> DatasetSpec:
    """Read a long-format CSV file and convert it to DatasetSpec."""
    rows_by_item: dict[str, list[tuple[str, float]]] = defaultdict(list)

    with spec.path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file is empty: {spec.path}")

        fieldnames = set(reader.fieldnames)
        required = {spec.timestamp_column, spec.target_column}
        missing = required - fieldnames
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"CSV file is missing required columns: {missing_text}")

        has_item_id = spec.item_id_column in fieldnames

        for row_index, row in enumerate(reader, start=2):
            item_id = row[spec.item_id_column] if has_item_id else "series_0"
            timestamp = row[spec.timestamp_column]
            target_text = row[spec.target_column]

            if item_id == "":
                raise ValueError(f"empty item_id at CSV line {row_index}")
            if timestamp == "":
                raise ValueError(f"empty timestamp at CSV line {row_index}")

            try:
                target = float(target_text)
            except ValueError as exc:
                raise ValueError(
                    f"invalid target value at CSV line {row_index}: {target_text}"
                ) from exc

            rows_by_item[item_id].append((timestamp, target))

    if not rows_by_item:
        raise ValueError(f"CSV file contains no data rows: {spec.path}")

    series = []
    for item_id in sorted(rows_by_item):
        rows = sorted(rows_by_item[item_id], key=lambda item: item[0])
        series.append(
            {
                "item_id": item_id,
                "start": rows[0][0],
                "target": [target for _, target in rows],
            }
        )

    return DatasetSpec.model_validate({"series": series})


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
