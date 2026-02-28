"""Abstract base class for all forecasters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ForecastResult:
    """Holds the output of a single series forecast."""

    dates: list[str]
    p50: list[float]
    p10: list[float] = field(default_factory=list)
    p90: list[float] = field(default_factory=list)
    model_name: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        n = len(self.dates)
        if not self.p10:
            # Default interval: ±20% of p50 as a rough placeholder
            self.p10 = [max(0.0, v * 0.8) for v in self.p50]
        if not self.p90:
            self.p90 = [v * 1.2 for v in self.p50]
        assert len(self.p50) == n, "p50 length mismatch"
        assert len(self.p10) == n, "p10 length mismatch"
        assert len(self.p90) == n, "p90 length mismatch"


class BaseForecaster(ABC):
    """Interface every forecasting model must implement."""

    name: str = "base"

    @abstractmethod
    def fit(self, X_train: pd.DataFrame, y_train: pd.Series) -> "BaseForecaster":
        """Train the model.

        Parameters
        ----------
        X_train:
            Feature matrix for training samples.
        y_train:
            Target values.

        Returns
        -------
        self
        """
        ...

    @abstractmethod
    def predict(self, X_future: pd.DataFrame) -> np.ndarray:
        """Generate point forecasts for the future feature frame.

        Parameters
        ----------
        X_future:
            Feature matrix for future time steps.

        Returns
        -------
        numpy array of length ``len(X_future)``.
        """
        ...

    def predict_intervals(
        self, X_future: pd.DataFrame, alpha: float = 0.2
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate (p10, p90) prediction intervals.

        Default implementation returns symmetric ±(alpha/2 * 100)% bounds
        around the point forecast.  Override for model-specific intervals.

        Returns
        -------
        (p10, p90) arrays of the same length as X_future.
        """
        p50 = self.predict(X_future)
        p10 = p50 * (1 - alpha / 2)
        p90 = p50 * (1 + alpha / 2)
        return np.maximum(p10, 0), p90

    def get_params(self) -> dict:
        """Return hyper-parameters for logging to MLflow."""
        return {}
