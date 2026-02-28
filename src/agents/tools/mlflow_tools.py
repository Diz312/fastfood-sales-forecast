"""MLflow query tools — sync MLflow client wrapped in asyncio.to_thread."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


def _get_best_run_sync(
    experiment_name: str, metric: str, ascending: bool
) -> dict:
    import mlflow

    from src.core.config import get_settings

    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        return {"error": f"Experiment '{experiment_name}' not found"}

    order = "ASC" if ascending else "DESC"
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=[f"metrics.{metric} {order}"],
        max_results=1,
        output_format="list",
    )
    if not runs:
        return {"error": "No runs found"}

    run = runs[0]
    return {
        "run_id": run.info.run_id,
        "run_name": run.info.run_name,
        "status": run.info.status,
        "metrics": {k: v for k, v in run.data.metrics.items() if "cv_" in k or "train_" in k},
        "params": run.data.params,
        "tags": {k: v for k, v in run.data.tags.items() if not k.startswith("mlflow.")},
    }


def _compare_runs_sync(run_ids: list[str]) -> dict:
    import mlflow

    from src.core.config import get_settings

    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    comparison = []
    for run_id in run_ids:
        try:
            run = mlflow.get_run(run_id)
            comparison.append(
                {
                    "run_id": run_id,
                    "run_name": run.info.run_name,
                    "metrics": {
                        k: v
                        for k, v in run.data.metrics.items()
                        if "cv_" in k or "train_" in k
                    },
                    "params": run.data.params,
                }
            )
        except Exception as exc:
            comparison.append({"run_id": run_id, "error": str(exc)})

    return {"runs": comparison, "count": len(comparison)}


async def get_best_run(
    experiment_name: str = "fastfood-forecast",
    metric: str = "cv_mase",
    ascending: bool = True,
) -> dict:
    return await asyncio.to_thread(_get_best_run_sync, experiment_name, metric, ascending)


async def compare_runs(run_ids: list[str]) -> dict:
    return await asyncio.to_thread(_compare_runs_sync, run_ids)
