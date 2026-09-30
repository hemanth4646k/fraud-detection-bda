from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split


def download_dataset(dataset_url: str, output_path: str | Path, force: bool = False) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        return destination
    with urllib.request.urlopen(dataset_url, timeout=120) as response:
        with destination.open("wb") as sink:
            shutil.copyfileobj(response, sink)
    return destination


def load_raw_dataset(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def split_dataframe(
    frame: pd.DataFrame,
    label_column: str = "Class",
    test_size: float = 0.2,
    validation_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_frame, test_frame = train_test_split(
        frame, test_size=test_size, stratify=frame[label_column], random_state=random_state,
    )
    validation_fraction = validation_size / (1 - test_size)
    train_frame, validation_frame = train_test_split(
        train_frame, test_size=validation_fraction,
        stratify=train_frame[label_column], random_state=random_state,
    )
    return (
        train_frame.reset_index(drop=True),
        validation_frame.reset_index(drop=True),
        test_frame.reset_index(drop=True),
    )


def save_streaming_seed(frame: pd.DataFrame, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return output_path
