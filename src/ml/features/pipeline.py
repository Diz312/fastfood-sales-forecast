"""Feature engineering pipeline.

Orchestrates calendar and lag feature steps. Returns a feature DataFrame
ready for model training or inference.
"""

from __future__ import annotations

import pandas as pd

from src.ml.features.calendar import CALENDAR_FEATURE_COLS, add_calendar_features
from src.ml.features.lag_features import LAG_FEATURE_COLS, add_lag_features

# All feature columns produced by this pipeline
ALL_FEATURE_COLS: list[str] = CALENDAR_FEATURE_COLS + LAG_FEATURE_COLS

TARGET_COL = "quantity"


def build_feature_matrix(
    sales_df: pd.DataFrame,
    date_col: str = "sale_date",
    target_col: str = TARGET_COL,
    group_cols: list[str] | None = None,
    drop_na_rows: bool = True,
) -> pd.DataFrame:
    """Transform raw daily sales data into a feature matrix.

    Parameters
    ----------
    sales_df:
        DataFrame with at minimum columns: ``[date_col, target_col,
        "restaurant_id", "sku_id"]``.  Must already be sorted by
        (group_cols, date_col) ascending.
    date_col:
        Name of the date column.
    target_col:
        Name of the target column.
    group_cols:
        Columns that identify a unique time series.  Defaults to
        ``["restaurant_id", "sku_id"]``.
    drop_na_rows:
        Whether to drop rows that have NaN in any feature column (typically
        the first few rows of each series that lack full lag history).

    Returns
    -------
    DataFrame with original columns plus all feature columns; sorted by
    (group_cols, date_col).
    """
    if group_cols is None:
        group_cols = ["restaurant_id", "sku_id"]

    df = sales_df.copy()

    # Ensure correct sort order before lag computation
    df = df.sort_values(group_cols + [date_col]).reset_index(drop=True)

    # Step 1: calendar features
    df = add_calendar_features(df, date_col=date_col)

    # Step 2: lag / rolling features
    df = add_lag_features(df, target_col=target_col, group_cols=group_cols, date_col=date_col)

    if drop_na_rows:
        # Drop rows where any lag feature is NaN (early rows per series)
        lag_cols = [c for c in LAG_FEATURE_COLS if c in df.columns]
        df = df.dropna(subset=lag_cols).reset_index(drop=True)

    return df


def get_feature_and_target(
    feature_df: pd.DataFrame,
    feature_cols: list[str] | None = None,
    target_col: str = TARGET_COL,
) -> tuple[pd.DataFrame, pd.Series]:
    """Split feature matrix into X and y.

    Parameters
    ----------
    feature_df:
        Output of :func:`build_feature_matrix`.
    feature_cols:
        Subset of feature columns to use.  Defaults to :data:`ALL_FEATURE_COLS`.
    target_col:
        Target column name.

    Returns
    -------
    (X, y) tuple.
    """
    if feature_cols is None:
        feature_cols = [c for c in ALL_FEATURE_COLS if c in feature_df.columns]

    X = feature_df[feature_cols].copy()
    y = feature_df[target_col].copy()
    return X, y


def build_future_frame(
    last_date: pd.Timestamp,
    horizon_days: int,
    restaurant_id: str,
    sku_id: str,
    history_df: pd.DataFrame,
    date_col: str = "sale_date",
    target_col: str = TARGET_COL,
) -> pd.DataFrame:
    """Build a future feature frame for inference.

    Creates a date range from ``last_date + 1`` to ``last_date + horizon_days``,
    adds calendar features, then back-fills lag features from ``history_df``
    (only calendar-based; lag features beyond the history are NaN-filled with
    the series mean as a fallback).

    Parameters
    ----------
    last_date:
        Last observed date in the training data.
    horizon_days:
        Number of future days to predict.
    restaurant_id:
        Restaurant UUID string.
    sku_id:
        SKU UUID string.
    history_df:
        Historical data for this (restaurant_id, sku_id) series, sorted
        ascending by date_col.
    date_col, target_col:
        Column names.

    Returns
    -------
    DataFrame with calendar features; lag features from history where
    available, else NaN (callers should fill before inference).
    """
    future_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1),
        periods=horizon_days,
        freq="D",
    )

    future_df = pd.DataFrame(
        {
            date_col: future_dates.date,
            "restaurant_id": restaurant_id,
            "sku_id": sku_id,
            target_col: float("nan"),
        }
    )

    # Combine history + future so rolling/lag can look back into history
    combined = pd.concat(
        [
            history_df[[date_col, "restaurant_id", "sku_id", target_col]].copy(),
            future_df,
        ],
        ignore_index=True,
    )
    combined[date_col] = pd.to_datetime(combined[date_col])
    combined = combined.sort_values(date_col).reset_index(drop=True)

    combined = add_calendar_features(combined, date_col=date_col)
    combined = add_lag_features(
        combined,
        target_col=target_col,
        group_cols=["restaurant_id", "sku_id"],
        date_col=date_col,
    )

    # Return only the future rows
    result = combined[combined[target_col].isna()].copy().reset_index(drop=True)

    # Fill remaining NaN lag values with mean of historical target
    hist_mean = history_df[target_col].mean()
    lag_cols = [c for c in LAG_FEATURE_COLS if c in result.columns]
    result[lag_cols] = result[lag_cols].fillna(hist_mean)

    return result
