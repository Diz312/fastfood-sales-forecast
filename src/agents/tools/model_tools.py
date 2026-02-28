"""Model selection and hyperparameter suggestion tools."""
from __future__ import annotations


async def select_model(restaurant_id: str, sku_id: str, data_length_days: int) -> dict:
    """Select the best forecasting model for a series.

    Sprint 1: always returns xgboost. Future sprints will add LightGBM,
    Prophet, LSTM selection logic based on series characteristics.
    """
    reason = "XGBoost is the only available model in Sprint 1"
    if data_length_days < 60:
        reason = f"Short series ({data_length_days} days) — XGBoost with conservative settings"

    return {
        "model_name": "xgboost",
        "reason": reason,
        "restaurant_id": restaurant_id,
        "sku_id": sku_id,
    }


async def suggest_hyperparams(model_name: str, series_length: int) -> dict:
    """Suggest hyperparameters for a forecasting model."""
    if model_name == "xgboost":
        if series_length < 90:
            # Conservative for short series
            params = {
                "n_estimators": 100,
                "max_depth": 3,
                "learning_rate": 0.05,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "min_child_weight": 5,
                "reg_alpha": 0.1,
                "reg_lambda": 1.0,
            }
        else:
            params = {
                "n_estimators": 300,
                "max_depth": 5,
                "learning_rate": 0.05,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "min_child_weight": 3,
                "reg_alpha": 0.05,
                "reg_lambda": 1.0,
            }
        return {"model_name": model_name, "series_length": series_length, "params": params}

    return {
        "model_name": model_name,
        "series_length": series_length,
        "params": {},
        "note": f"No hyperparameter suggestions available for {model_name}",
    }
