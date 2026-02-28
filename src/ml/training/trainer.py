"""MLflow-logged training loop.

Trains a forecaster using expanding-window CV, logs each fold's metrics,
then trains a final model on all data and registers it in the MLflow
model registry.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd

from src.core.config import get_settings
from src.ml.evaluation.metrics import compute_all_metrics
from src.ml.features.pipeline import (
    ALL_FEATURE_COLS,
    TARGET_COL,
    build_feature_matrix,
    build_future_frame,
    get_feature_and_target,
)
from src.ml.models.base import BaseForecaster, ForecastResult
from src.ml.models.xgboost_model import XGBoostForecaster
from src.ml.training.cross_validation import CVFold, expanding_window_splits

logger = logging.getLogger(__name__)

EXPERIMENT_NAME = "fastfood-forecast"


@dataclass
class TrainConfig:
    """Configuration for a training run."""

    horizon_days: int = 365
    n_cv_folds: int = 4
    val_size_days: int = 28
    min_train_days: int = 60
    seasonality: int = 7
    model_name: str = "xgboost"
    model_params: dict = field(default_factory=dict)
    register_model: bool = True


@dataclass
class SeriesTrainResult:
    """Result for a single (restaurant_id, sku_id) series."""

    restaurant_id: str
    sku_id: str
    model_name: str
    mlflow_run_id: str
    cv_metrics: dict[str, float]
    forecast: ForecastResult
    feature_importances: dict[str, float] = field(default_factory=dict)


def _get_or_create_experiment(experiment_name: str) -> str:
    """Return the experiment ID, creating it if needed."""
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        return mlflow.create_experiment(experiment_name)
    return experiment.experiment_id


def _make_forecaster(model_name: str, params: dict) -> BaseForecaster:
    if model_name == "xgboost":
        return XGBoostForecaster(params=params or None)
    raise ValueError(f"Unknown model: {model_name}")


def train_single_series(
    sales_df: pd.DataFrame,
    restaurant_id: str,
    sku_id: str,
    config: TrainConfig,
    forecast_run_id: str,
) -> SeriesTrainResult:
    """Train and evaluate a forecaster for one (restaurant_id, sku_id) series.

    Parameters
    ----------
    sales_df:
        Full historical sales for this series (already filtered to the
        given restaurant/SKU).  Must contain ``sale_date`` and ``quantity``.
    restaurant_id, sku_id:
        Identity of the series.
    config:
        Training configuration.
    forecast_run_id:
        The parent forecast run UUID (for MLflow tagging).

    Returns
    -------
    :class:`SeriesTrainResult` with CV metrics, final model artifacts, and
    the future forecast.
    """
    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    experiment_id = _get_or_create_experiment(EXPERIMENT_NAME)

    series_key = f"rest={restaurant_id[:8]}_sku={sku_id[:8]}"
    run_name = f"{config.model_name}_{series_key}"

    with mlflow.start_run(
        experiment_id=experiment_id,
        run_name=run_name,
        tags={
            "forecast_run_id": forecast_run_id,
            "restaurant_id": restaurant_id,
            "sku_id": sku_id,
            "model_name": config.model_name,
        },
    ) as mlflow_run:
        mlflow_run_id = mlflow_run.info.run_id

        # Log config
        mlflow.log_params(
            {
                "model_name": config.model_name,
                "horizon_days": config.horizon_days,
                "n_cv_folds": config.n_cv_folds,
                "val_size_days": config.val_size_days,
                **{f"model_{k}": v for k, v in config.model_params.items()},
            }
        )

        # ---------------------------------------------------------------
        # Build full feature matrix
        # ---------------------------------------------------------------
        feature_df = build_feature_matrix(
            sales_df,
            date_col="sale_date",
            target_col=TARGET_COL,
            drop_na_rows=True,
        )

        feature_cols = [c for c in ALL_FEATURE_COLS if c in feature_df.columns]

        # ---------------------------------------------------------------
        # Expanding-window cross-validation
        # ---------------------------------------------------------------
        try:
            folds: list[CVFold] = expanding_window_splits(
                feature_df,
                date_col="sale_date",
                n_folds=config.n_cv_folds,
                val_size_days=config.val_size_days,
                min_train_days=config.min_train_days,
            )
        except ValueError as exc:
            logger.warning("Skipping CV for %s: %s", series_key, exc)
            folds = []

        fold_metrics: list[dict[str, float]] = []
        for fold in folds:
            X_train, y_train = get_feature_and_target(fold.train_df, feature_cols)
            X_val, y_val = get_feature_and_target(fold.val_df, feature_cols)

            model = _make_forecaster(config.model_name, config.model_params)
            model.fit(X_train, y_train)

            preds = model.predict(X_val)
            p10, p90 = model.predict_intervals(X_val)

            fold_m = compute_all_metrics(
                actuals=y_val.values,
                p50=preds,
                p10=p10,
                p90=p90,
                naive_actuals=y_train.values,
                seasonality=config.seasonality,
            )
            fold_metrics.append(fold_m)

            # Log per-fold metrics with fold index suffix
            mlflow.log_metrics(
                {f"fold{fold.fold_idx}_{k}": v for k, v in fold_m.items() if not np.isnan(v)}
            )

        # Average CV metrics
        cv_metrics: dict[str, float] = {}
        if fold_metrics:
            all_keys = fold_metrics[0].keys()
            cv_metrics = {
                k: float(np.nanmean([fm[k] for fm in fold_metrics]))
                for k in all_keys
            }
            mlflow.log_metrics({f"cv_{k}": v for k, v in cv_metrics.items() if not np.isnan(v)})
        else:
            logger.warning("No CV folds completed for %s", series_key)

        # ---------------------------------------------------------------
        # Final model: train on all available data
        # ---------------------------------------------------------------
        X_all, y_all = get_feature_and_target(feature_df, feature_cols)
        final_model = _make_forecaster(config.model_name, config.model_params)
        final_model.fit(X_all, y_all)

        # Log final in-sample metrics
        in_sample_preds = final_model.predict(X_all)
        in_sample_m = compute_all_metrics(
            actuals=y_all.values,
            p50=in_sample_preds,
            naive_actuals=y_all.values,
            seasonality=config.seasonality,
        )
        mlflow.log_metrics(
            {f"train_{k}": v for k, v in in_sample_m.items() if not np.isnan(v)}
        )

        # Log model artifact
        if config.model_name == "xgboost":
            mlflow.xgboost.log_model(
                xgb_model=final_model._model,  # type: ignore[attr-defined]
                artifact_path="model",
                registered_model_name=f"{EXPERIMENT_NAME}-{config.model_name}" if config.register_model else None,
            )

        # Log feature importances
        feature_importances: dict[str, float] = {}
        if hasattr(final_model, "feature_importances"):
            feature_importances = final_model.feature_importances  # type: ignore[attr-defined]
            mlflow.log_dict(feature_importances, "feature_importances.json")

        # ---------------------------------------------------------------
        # Generate future forecast
        # ---------------------------------------------------------------
        last_date = pd.to_datetime(sales_df["sale_date"]).max()
        future_frame = build_future_frame(
            last_date=last_date,
            horizon_days=config.horizon_days,
            restaurant_id=restaurant_id,
            sku_id=sku_id,
            history_df=sales_df,
        )

        future_feature_cols = [c for c in feature_cols if c in future_frame.columns]
        X_future = future_frame[future_feature_cols]

        p50_arr = final_model.predict(X_future)
        p10_arr, p90_arr = final_model.predict_intervals(X_future)

        future_dates = [str(d.date()) for d in pd.to_datetime(future_frame["sale_date"])]

        forecast = ForecastResult(
            dates=future_dates,
            p50=p50_arr.tolist(),
            p10=p10_arr.tolist(),
            p90=p90_arr.tolist(),
            model_name=config.model_name,
            metadata={
                "mlflow_run_id": mlflow_run_id,
                "cv_metrics": cv_metrics,
            },
        )

        # Log forecast summary artifact
        mlflow.log_dict(
            {
                "restaurant_id": restaurant_id,
                "sku_id": sku_id,
                "horizon_days": config.horizon_days,
                "cv_metrics": cv_metrics,
                "forecast_dates_head": future_dates[:7],
                "forecast_p50_head": forecast.p50[:7],
            },
            "forecast_summary.json",
        )

    return SeriesTrainResult(
        restaurant_id=restaurant_id,
        sku_id=sku_id,
        model_name=config.model_name,
        mlflow_run_id=mlflow_run_id,
        cv_metrics=cv_metrics,
        forecast=forecast,
        feature_importances=feature_importances,
    )


def train_all_series(
    all_sales_df: pd.DataFrame,
    config: TrainConfig,
    forecast_run_id: str | None = None,
) -> list[SeriesTrainResult]:
    """Train a forecaster for every unique (restaurant_id, sku_id) series.

    Parameters
    ----------
    all_sales_df:
        Full historical sales table, all restaurants and SKUs.
    config:
        Shared training configuration.
    forecast_run_id:
        Parent forecast run UUID; generated if not provided.

    Returns
    -------
    List of :class:`SeriesTrainResult`, one per series.
    """
    if forecast_run_id is None:
        forecast_run_id = str(uuid.uuid4())

    series_keys = all_sales_df.groupby(["restaurant_id", "sku_id"]).size().index.tolist()
    logger.info("Training %d series (forecast_run=%s)", len(series_keys), forecast_run_id)

    results: list[SeriesTrainResult] = []
    for restaurant_id, sku_id in series_keys:
        mask = (all_sales_df["restaurant_id"] == restaurant_id) & (
            all_sales_df["sku_id"] == sku_id
        )
        series_df = all_sales_df[mask].sort_values("sale_date").reset_index(drop=True)

        try:
            result = train_single_series(
                sales_df=series_df,
                restaurant_id=str(restaurant_id),
                sku_id=str(sku_id),
                config=config,
                forecast_run_id=forecast_run_id,
            )
            results.append(result)
            logger.info(
                "Trained %s/%s: MASE=%.3f SMAPE=%.1f",
                restaurant_id,
                sku_id,
                result.cv_metrics.get("mase", float("nan")),
                result.cv_metrics.get("smape", float("nan")),
            )
        except Exception:
            logger.exception("Failed training series %s/%s", restaurant_id, sku_id)

    return results
