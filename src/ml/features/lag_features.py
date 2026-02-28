"""Lag and rolling-window feature engineering.

Requires data to be sorted by (restaurant_id, sku_id, sale_date) before calling.
All lag/rolling features are computed per (restaurant_id, sku_id) group.
"""

from __future__ import annotations

import pandas as pd

# Lag windows in days
LAG_WINDOWS: list[int] = [7, 14, 28]

# Rolling window sizes in days
ROLLING_WINDOWS: list[int] = [7, 14, 28]

LAG_FEATURE_COLS: list[str] = (
    [f"lag_{w}" for w in LAG_WINDOWS]
    + [f"rolling_mean_{w}" for w in ROLLING_WINDOWS]
    + [f"rolling_std_{w}" for w in ROLLING_WINDOWS]
    + [f"rolling_min_{w}" for w in ROLLING_WINDOWS]
    + [f"rolling_max_{w}" for w in ROLLING_WINDOWS]
)


def add_lag_features(
    df: pd.DataFrame,
    target_col: str = "quantity",
    group_cols: list[str] | None = None,
    date_col: str = "sale_date",
) -> pd.DataFrame:
    """Add lag and rolling features to *df* in-place and return it.

    Parameters
    ----------
    df:
        Must be sorted by (*group_cols*, *date_col*) ascending before calling.
        Must contain *target_col*.
    target_col:
        Column to lag / roll over (typically ``"quantity"``).
    group_cols:
        Columns that define a time series identity. Defaults to
        ``["restaurant_id", "sku_id"]``.
    date_col:
        Date column name (used only for sort verification logging).

    Returns
    -------
    df with lag and rolling columns added. Rows with insufficient history will
    have NaN in the corresponding columns.
    """
    if group_cols is None:
        group_cols = ["restaurant_id", "sku_id"]

    grp = df.groupby(group_cols, sort=False)[target_col]

    # Lag features
    for w in LAG_WINDOWS:
        df[f"lag_{w}"] = grp.shift(w)

    # Rolling features (min_periods=1 avoids dropping rows with sparse history)
    for w in ROLLING_WINDOWS:
        rolled = grp.shift(1).groupby(df[group_cols].apply(tuple, axis=1))
        # Use transform for group-aware rolling
        df[f"rolling_mean_{w}"] = (
            df.groupby(group_cols, sort=False)[target_col]
            .transform(lambda s: s.shift(1).rolling(w, min_periods=1).mean())
        )
        df[f"rolling_std_{w}"] = (
            df.groupby(group_cols, sort=False)[target_col]
            .transform(lambda s: s.shift(1).rolling(w, min_periods=1).std().fillna(0))
        )
        df[f"rolling_min_{w}"] = (
            df.groupby(group_cols, sort=False)[target_col]
            .transform(lambda s: s.shift(1).rolling(w, min_periods=1).min())
        )
        df[f"rolling_max_{w}"] = (
            df.groupby(group_cols, sort=False)[target_col]
            .transform(lambda s: s.shift(1).rolling(w, min_periods=1).max())
        )

    return df
