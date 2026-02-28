"""Forecast evaluation metrics.

All functions accept numpy arrays or pandas Series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def mase(
    actuals: np.ndarray | pd.Series,
    forecasts: np.ndarray | pd.Series,
    naive_actuals: np.ndarray | pd.Series | None = None,
    seasonality: int = 7,
) -> float:
    """Mean Absolute Scaled Error.

    Scales MAE by the naive seasonal forecast (seasonal random walk) MAE.

    Parameters
    ----------
    actuals:
        True observed values.
    forecasts:
        Predicted values (same length as *actuals*).
    naive_actuals:
        Training data used to compute the naive scale. If None, the actuals
        themselves are used with lag=``seasonality`` (appropriate for test sets
        that immediately follow the training window).
    seasonality:
        Seasonal period for the naive forecast (7 for daily data with weekly
        seasonality).

    Returns
    -------
    float, MASE ≥ 0. Values < 1 indicate the model beats the naive baseline.
    """
    y = np.asarray(actuals, dtype=float)
    yhat = np.asarray(forecasts, dtype=float)

    mae = np.mean(np.abs(y - yhat))

    if naive_actuals is not None:
        yn = np.asarray(naive_actuals, dtype=float)
    else:
        yn = y

    scale_errors = np.abs(yn[seasonality:] - yn[:-seasonality])
    scale = np.mean(scale_errors)

    if scale < 1e-10:
        return float("nan")

    return float(mae / scale)


def smape(
    actuals: np.ndarray | pd.Series,
    forecasts: np.ndarray | pd.Series,
) -> float:
    """Symmetric Mean Absolute Percentage Error (0-200 scale).

    Returns
    -------
    float in [0, 200].
    """
    y = np.asarray(actuals, dtype=float)
    yhat = np.asarray(forecasts, dtype=float)

    denom = (np.abs(y) + np.abs(yhat)) / 2
    mask = denom > 1e-10
    if not mask.any():
        return float("nan")

    return float(np.mean(np.abs(y[mask] - yhat[mask]) / denom[mask]) * 100)


def wql(
    actuals: np.ndarray | pd.Series,
    p10: np.ndarray | pd.Series,
    p90: np.ndarray | pd.Series,
) -> float:
    """Weighted Quantile Loss (also called Interval Score proxy).

    Averages pinball loss at q=0.1 and q=0.9.

    Returns
    -------
    float ≥ 0.
    """
    y = np.asarray(actuals, dtype=float)
    q10 = np.asarray(p10, dtype=float)
    q90 = np.asarray(p90, dtype=float)

    def pinball(q: float, lower: np.ndarray) -> np.ndarray:
        errors = y - lower
        return np.where(errors >= 0, q * errors, (q - 1) * errors)

    loss = (pinball(0.1, q10) + pinball(0.9, q90)).mean()
    return float(loss)


def coverage_80(
    actuals: np.ndarray | pd.Series,
    p10: np.ndarray | pd.Series,
    p90: np.ndarray | pd.Series,
) -> float:
    """Fraction of actuals within the [p10, p90] prediction interval.

    Ideal value: 0.80. Returns float in [0, 1].
    """
    y = np.asarray(actuals, dtype=float)
    lo = np.asarray(p10, dtype=float)
    hi = np.asarray(p90, dtype=float)
    return float(np.mean((y >= lo) & (y <= hi)))


def compute_all_metrics(
    actuals: np.ndarray | pd.Series,
    p50: np.ndarray | pd.Series,
    p10: np.ndarray | pd.Series | None = None,
    p90: np.ndarray | pd.Series | None = None,
    naive_actuals: np.ndarray | pd.Series | None = None,
    seasonality: int = 7,
) -> dict[str, float]:
    """Compute all metrics at once.

    Returns
    -------
    Dict with keys: ``mase``, ``smape``, ``wql`` (if p10/p90 given),
    ``coverage_80`` (if p10/p90 given).
    """
    metrics: dict[str, float] = {
        "mase": mase(actuals, p50, naive_actuals=naive_actuals, seasonality=seasonality),
        "smape": smape(actuals, p50),
    }

    if p10 is not None and p90 is not None:
        metrics["wql"] = wql(actuals, p10, p90)
        metrics["coverage_80"] = coverage_80(actuals, p10, p90)

    return metrics
