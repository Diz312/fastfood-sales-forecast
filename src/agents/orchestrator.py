"""Anthropic SDK orchestrator with manual tool use loop.

Model: claude-opus-4-6 with adaptive thinking.
Emits events to an asyncio.Queue consumed by the SSE endpoint.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_sales_summary",
        "description": "Get aggregate sales statistics from the database (total rows, date range, restaurants, SKUs).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_series_stats",
        "description": "Get statistics for a specific restaurant/SKU series (mean, std, min, max quantity).",
        "input_schema": {
            "type": "object",
            "properties": {
                "restaurant_id": {"type": "string", "description": "UUID of the restaurant"},
                "sku_id": {"type": "string", "description": "UUID of the SKU"},
            },
            "required": ["restaurant_id", "sku_id"],
        },
    },
    {
        "name": "select_model",
        "description": "Select the best forecasting model for a series based on its characteristics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "restaurant_id": {"type": "string"},
                "sku_id": {"type": "string"},
                "data_length_days": {"type": "integer", "description": "Number of days of history"},
            },
            "required": ["restaurant_id", "sku_id", "data_length_days"],
        },
    },
    {
        "name": "suggest_hyperparams",
        "description": "Suggest hyperparameters for a forecasting model given series length.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string", "description": "e.g. xgboost"},
                "series_length": {"type": "integer", "description": "Number of training days"},
            },
            "required": ["model_name", "series_length"],
        },
    },
    {
        "name": "get_best_run",
        "description": "Get the best MLflow run for an experiment ordered by a metric.",
        "input_schema": {
            "type": "object",
            "properties": {
                "experiment_name": {"type": "string", "default": "fastfood-forecast"},
                "metric": {"type": "string", "default": "cv_mase"},
                "ascending": {
                    "type": "boolean",
                    "default": True,
                    "description": "True = lower is better (MASE, SMAPE)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "trigger_forecast",
        "description": "Trigger a new forecast pipeline run via Celery.",
        "input_schema": {
            "type": "object",
            "properties": {
                "horizon_days": {"type": "integer", "default": 365},
                "triggered_by": {"type": "string", "default": "agent"},
            },
            "required": [],
        },
    },
    {
        "name": "get_forecast_values",
        "description": "Get a summary of forecast values for a completed run.",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "UUID of the forecast run"},
                "sku_id": {
                    "type": "string",
                    "description": "Optional: filter to a specific SKU UUID",
                },
            },
            "required": ["run_id"],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


async def _dispatch_tool(
    name: str,
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    from src.agents.tools.data_tools import get_sales_summary, get_series_stats
    from src.agents.tools.forecast_tools import get_forecast_values, trigger_forecast
    from src.agents.tools.mlflow_tools import compare_runs, get_best_run
    from src.agents.tools.model_tools import select_model, suggest_hyperparams

    try:
        if name == "get_sales_summary":
            return await get_sales_summary(db)
        elif name == "get_series_stats":
            return await get_series_stats(db, **tool_input)
        elif name == "select_model":
            return await select_model(**tool_input)
        elif name == "suggest_hyperparams":
            return await suggest_hyperparams(**tool_input)
        elif name == "get_best_run":
            return await get_best_run(**tool_input)
        elif name == "compare_runs":
            return await compare_runs(**tool_input)
        elif name == "trigger_forecast":
            return await trigger_forecast(db, **tool_input)
        elif name == "get_forecast_values":
            return await get_forecast_values(db, **tool_input)
        else:
            return {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def run_orchestrator(
    prompt: str,
    stream_id: str,
    queue: asyncio.Queue,
    db: AsyncSession,
) -> None:
    """Run the claude-opus-4-6 tool use loop and emit events to queue."""
    settings = get_settings()

    def _emit(event_type: str, data: dict[str, Any]) -> None:
        queue.put_nowait(
            {
                "event_type": event_type,
                "stream_id": stream_id,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

    system_prompt = (
        "You are a sales forecasting analyst for a fast food restaurant chain. "
        "You have access to tools to query sales data, select models, check MLflow runs, "
        "and trigger forecasts. Be concise and data-driven in your analysis. "
        "When asked to run a forecast, use trigger_forecast and then report the run_id."
    )

    try:
        while True:
            response = await client.messages.create(
                model="claude-opus-4-6",
                max_tokens=8192,
                thinking={"type": "adaptive"},
                system=system_prompt,
                tools=TOOL_DEFINITIONS,  # type: ignore[arg-type]
                messages=messages,
            )

            # Emit content blocks
            assistant_content: list[Any] = []
            for block in response.content:
                assistant_content.append(block)
                if block.type == "thinking":
                    _emit("thinking", {"text": block.thinking})
                elif block.type == "text":
                    _emit("message", {"text": block.text})

            if response.stop_reason == "end_turn":
                _emit("done", {"message": "Agent finished"})
                break

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": assistant_content})
                tool_results: list[dict[str, Any]] = []

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    _emit(
                        "tool_call",
                        {"name": block.name, "input": block.input, "tool_use_id": block.id},
                    )

                    result = await _dispatch_tool(block.name, block.input, db)

                    _emit("tool_result", {"name": block.name, "result": result})

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )

                messages.append({"role": "user", "content": tool_results})
            else:
                _emit("done", {"message": f"Stopped: {response.stop_reason}"})
                break

    except Exception as exc:
        logger.exception("Orchestrator error for stream %s", stream_id)
        _emit("error", {"message": str(exc)})
