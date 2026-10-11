from __future__ import annotations

from pathlib import Path

from typing import Optional

import pandas as pd

from .config import Settings


def _recent_parquet_files(base_path: Path, max_files: Optional[int] = None) -> list[Path]:
    if not base_path.exists():
        return []
    files = [
        path
        for path in base_path.rglob("*.parquet")
        if "_spark_metadata" not in path.parts
    ]
    files = sorted(files, key=lambda item: item.stat().st_mtime, reverse=True)
    if max_files is not None:
        files = files[:max_files]
    return files


def load_parquet_directory(base_path: Path, max_files: Optional[int] = None) -> pd.DataFrame:
    files = _recent_parquet_files(base_path, max_files=max_files)
    if not files:
        return pd.DataFrame()

    frames = [pd.read_parquet(path) for path in reversed(files)]
    combined = pd.concat(frames, ignore_index=True)
    for column in ("processed_at", "event_ts"):
        if column in combined.columns:
            combined[column] = pd.to_datetime(combined[column], errors="coerce")
    return combined


def load_dashboard_frames(settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    predictions = load_parquet_directory(
        settings.dashboard_predictions_path,
        max_files=settings.dashboard_max_files,
    )
    alerts = load_parquet_directory(
        settings.dashboard_alerts_path,
        max_files=settings.dashboard_max_files,
    )
    return predictions, alerts
