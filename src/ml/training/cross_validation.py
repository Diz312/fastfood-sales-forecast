"""Expanding-window time series cross-validation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class CVFold:
    """Single cross-validation fold."""

    fold_idx: int
    train_df: pd.DataFrame
    val_df: pd.DataFrame
    train_end_date: pd.Timestamp
    val_start_date: pd.Timestamp
    val_end_date: pd.Timestamp


def expanding_window_splits(
    df: pd.DataFrame,
    date_col: str = "sale_date",
    n_folds: int = 4,
    val_size_days: int = 28,
    min_train_days: int = 60,
) -> list[CVFold]:
    """Generate expanding-window CV folds.

    The available data is divided into ``n_folds`` validation windows of
    ``val_size_days`` each, placed at the tail of the time series.  The
    training window expands from a minimum of ``min_train_days`` up to
    the day before each validation window.

    Parameters
    ----------
    df:
        Full feature DataFrame.  Must contain *date_col*.
    date_col:
        Date column name.
    n_folds:
        Number of CV folds.
    val_size_days:
        Validation window length in days (e.g. 28 for 4 weeks).
    min_train_days:
        Minimum training window size.  Folds that would require less
        training data are skipped.

    Returns
    -------
    List of :class:`CVFold`, oldest-first.
    """
    dates = pd.to_datetime(df[date_col])
    max_date = dates.max()
    min_date = dates.min()

    total_days = (max_date - min_date).days + 1
    required = min_train_days + n_folds * val_size_days
    if total_days < required:
        raise ValueError(
            f"Not enough data: need {required} days, have {total_days}. "
            f"Reduce n_folds ({n_folds}) or val_size_days ({val_size_days})."
        )

    folds: list[CVFold] = []
    for fold_idx in range(n_folds):
        # Each fold's validation window is placed counting back from max_date
        val_end = max_date - pd.Timedelta(days=fold_idx * val_size_days)
        val_start = val_end - pd.Timedelta(days=val_size_days - 1)
        train_end = val_start - pd.Timedelta(days=1)

        train_mask = (dates >= min_date) & (dates <= train_end)
        val_mask = (dates >= val_start) & (dates <= val_end)

        train_df = df[train_mask].copy()
        val_df = df[val_mask].copy()

        if len(train_df) < min_train_days or len(val_df) == 0:
            continue

        folds.append(
            CVFold(
                fold_idx=fold_idx,
                train_df=train_df,
                val_df=val_df,
                train_end_date=train_end,
                val_start_date=val_start,
                val_end_date=val_end,
            )
        )

    # Return oldest-first (fold with the most history last)
    return list(reversed(folds))
