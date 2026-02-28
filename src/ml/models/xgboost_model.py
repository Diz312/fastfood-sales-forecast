"""XGBoost forecaster wrapper."""

from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb

from src.ml.models.base import BaseForecaster

# Default hyper-parameters tuned for daily food-service time series
DEFAULT_PARAMS: dict = {
    "n_estimators": 400,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "objective": "reg:squarederror",
    "eval_metric": "rmse",
    "random_state": 42,
    "n_jobs": -1,
    "tree_method": "hist",
}


class XGBoostForecaster(BaseForecaster):
    """XGBoost gradient-boosted tree forecaster.

    Wraps ``xgboost.XGBRegressor`` with early-stopping support and
    a symmetric ±sigma prediction interval.

    Parameters
    ----------
    params:
        Override any key from :data:`DEFAULT_PARAMS`.
    early_stopping_rounds:
        Activate early stopping when > 0 and ``eval_set`` is provided to fit.
        Disabled by default to keep the interface simple for CV folds.
    """

    name = "xgboost"

    def __init__(
        self,
        params: dict | None = None,
        early_stopping_rounds: int = 0,
    ) -> None:
        merged = {**DEFAULT_PARAMS, **(params or {})}
        # Remove non-XGBRegressor keys that we manage ourselves
        self._early_stopping_rounds = early_stopping_rounds
        self._model = xgb.XGBRegressor(**merged)
        self._params = merged
        self._residual_std: float = 0.0

    # ------------------------------------------------------------------
    # BaseForecaster interface
    # ------------------------------------------------------------------

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        eval_set: list[tuple] | None = None,
    ) -> "XGBoostForecaster":
        """Fit the XGBoost model.

        Parameters
        ----------
        X_train, y_train:
            Training data.
        eval_set:
            Optional validation set for early stopping, e.g.
            ``[(X_val, y_val)]``.
        """
        fit_kwargs: dict = {}
        if eval_set and self._early_stopping_rounds > 0:
            fit_kwargs["eval_set"] = eval_set
            fit_kwargs["early_stopping_rounds"] = self._early_stopping_rounds
            fit_kwargs["verbose"] = False

        self._model.fit(X_train, y_train, **fit_kwargs)

        # Compute in-sample residual std for interval estimation
        preds = self._model.predict(X_train)
        residuals = y_train.values - preds
        self._residual_std = float(np.std(residuals))

        return self

    def predict(self, X_future: pd.DataFrame) -> np.ndarray:
        preds = self._model.predict(X_future)
        return np.maximum(preds, 0.0)  # clip negative quantities

    def predict_intervals(
        self, X_future: pd.DataFrame, alpha: float = 0.2
    ) -> tuple[np.ndarray, np.ndarray]:
        """Prediction intervals based on in-sample residual std (Gaussian approx).

        alpha is ignored; uses ±1.645σ for 90% interval.
        """
        p50 = self.predict(X_future)
        z = 1.645  # 90% symmetric interval
        p10 = np.maximum(p50 - z * self._residual_std, 0.0)
        p90 = p50 + z * self._residual_std
        return p10, p90

    def get_params(self) -> dict:
        return {f"xgb_{k}": v for k, v in self._params.items()}

    @property
    def feature_importances(self) -> dict[str, float]:
        """Return feature → importance score mapping."""
        booster = self._model.get_booster()
        scores = booster.get_score(importance_type="gain")
        return scores
