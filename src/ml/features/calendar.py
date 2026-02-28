"""Calendar-based feature engineering.

Produces day-of-week, month, quarter, Fourier seasonality terms,
and US public holiday indicators for a given date index.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import holidays as holidays_lib

    _HAS_HOLIDAYS = True
except ImportError:
    _HAS_HOLIDAYS = False


def add_calendar_features(df: pd.DataFrame, date_col: str = "sale_date") -> pd.DataFrame:
    """Append calendar features to *df* in-place and return it.

    Parameters
    ----------
    df:
        DataFrame that must contain *date_col* as a date/datetime column.
    date_col:
        Name of the date column.

    Returns
    -------
    df with added columns:
        - dow: day of week (0=Mon … 6=Sun)
        - dow_sin, dow_cos: cyclic encoding of day-of-week
        - month: month number (1-12)
        - month_sin, month_cos: cyclic encoding of month
        - quarter: quarter (1-4)
        - week_of_year: ISO week number (1-53)
        - day_of_year: day of year (1-366)
        - is_weekend: 1 if Saturday or Sunday, else 0
        - is_holiday_us: 1 if US federal holiday, else 0
        - fourier_week_sin_{k}, fourier_week_cos_{k}: weekly Fourier terms (k=1)
        - fourier_year_sin_{k}, fourier_year_cos_{k}: annual Fourier terms (k=1,2,3)
    """
    dates = pd.to_datetime(df[date_col])

    df["dow"] = dates.dt.dayofweek
    df["dow_sin"] = np.sin(2 * np.pi * df["dow"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dow"] / 7)

    df["month"] = dates.dt.month
    df["month_sin"] = np.sin(2 * np.pi * (df["month"] - 1) / 12)
    df["month_cos"] = np.cos(2 * np.pi * (df["month"] - 1) / 12)

    df["quarter"] = dates.dt.quarter
    df["week_of_year"] = dates.dt.isocalendar().week.astype(int)
    df["day_of_year"] = dates.dt.dayofyear
    df["is_weekend"] = (dates.dt.dayofweek >= 5).astype(int)

    # Holiday indicator
    if _HAS_HOLIDAYS:
        us_holidays = holidays_lib.US()
        df["is_holiday_us"] = dates.dt.date.apply(lambda d: int(d in us_holidays))
    else:
        df["is_holiday_us"] = 0

    # Fourier terms — weekly seasonality (period 7)
    day_seq = dates.dt.dayofyear.values  # proxy ordinal; consistent across years
    ordinal = np.array([d.toordinal() for d in dates.dt.date])
    df["fourier_week_sin_1"] = np.sin(2 * np.pi * 1 * ordinal / 7)
    df["fourier_week_cos_1"] = np.cos(2 * np.pi * 1 * ordinal / 7)

    # Fourier terms — annual seasonality (period 365.25), 3 harmonics
    for k in range(1, 4):
        df[f"fourier_year_sin_{k}"] = np.sin(2 * np.pi * k * day_seq / 365.25)
        df[f"fourier_year_cos_{k}"] = np.cos(2 * np.pi * k * day_seq / 365.25)

    return df


CALENDAR_FEATURE_COLS: list[str] = [
    "dow",
    "dow_sin",
    "dow_cos",
    "month",
    "month_sin",
    "month_cos",
    "quarter",
    "week_of_year",
    "day_of_year",
    "is_weekend",
    "is_holiday_us",
    "fourier_week_sin_1",
    "fourier_week_cos_1",
    "fourier_year_sin_1",
    "fourier_year_cos_1",
    "fourier_year_sin_2",
    "fourier_year_cos_2",
    "fourier_year_sin_3",
    "fourier_year_cos_3",
]
