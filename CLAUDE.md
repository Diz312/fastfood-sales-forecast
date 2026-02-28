# Sales Forecasting — Project Context

## What It Does
Full-stack fast food daily sales forecasting application. Predicts 12 months of sales at Restaurant × SKU
level with hierarchical reconciliation (MinT). Uses ML agents built on Anthropic SDK for feature
engineering, model selection, and drift detection.

## Stack
- **Backend**: FastAPI + Python 3.11 + uv
- **DB**: PostgreSQL (SQLAlchemy async + Alembic)
- **Queue**: Celery + Redis
- **ML**: XGBoost (Sprint 1), LightGBM, Prophet, LSTM, TFT + Optuna HPO (Sprint 2+)
- **MLOps**: MLflow + MinIO
- **Agents**: Anthropic SDK (`anthropic` package, manual tool use loop) — claude-opus-4-6
- **Frontend**: Next.js 15 App Router + TypeScript + shadcn/ui + Recharts
- **Deploy**: Local Docker Compose

## Key Commands
```bash
make up          # Start all services
make seed        # Generate synthetic data
make forecast    # Trigger forecast run via API
make migrate     # Run DB migrations
make test        # Run test suite
make logs        # Tail all logs
make shell       # Shell into API container
```

## File Structure
```
src/
  api/           # FastAPI routers + Pydantic schemas (source of truth for types)
  agents/        # Anthropic SDK orchestrator + tool functions
    tools/       # Deterministic tool functions agents call
  ml/            # Feature engineering, models, reconciliation, evaluation
    features/    # calendar.py, lag_features.py, pipeline.py
    models/      # base.py (ABC), xgboost_model.py
    training/    # cross_validation.py, trainer.py (MLflow-logged)
    evaluation/  # metrics.py (MASE, SMAPE, wQL, coverage_80)
    reconciliation/  # (placeholder, MinT Sprint 2)
  workers/       # Celery app + tasks
  db/            # SQLAlchemy ORM models + Alembic migrations
  core/          # Config (Pydantic Settings), logging (structlog), exceptions
  scripts/       # seed_synthetic.py, generate_ts_types.py
frontend/        # Next.js 15 App Router
tests/           # pytest unit + integration + e2e
```

## Sprint 1 Scope (Vertical Slice)
- 1 restaurant × 5 SKUs × 180 days synthetic data
- XGBoost model only (fastest to validate architecture)
- Simplified orchestrator agent (no sub-agents yet)
- OLS reconciliation placeholder (MinT in Sprint 2)
- Frontend pages: dashboard, agents event stream

## Architecture Decisions
- **Agents use `anthropic` SDK with manual tool use loop** — NOT `claude-agent-sdk` which wraps
  Claude Code CLI and requires it to be installed. We need custom ML tools.
- **SSE for agent streaming** — unidirectional, works through any HTTP proxy, native browser EventSource
- **PostgreSQL from day 1** — 36M rows at scale + MLflow needs it; SQLite unsuitable
- **Celery for ML jobs** — training survives API restarts, horizontal worker scaling
- **Pydantic schemas = TypeScript source of truth** — auto-generated via datamodel-codegen
- **claude-opus-4-6** for orchestrator with `thinking: {type: "adaptive"}` (NO budget_tokens — deprecated)
- **claude-sonnet-4-6** for sub-agents

## Service Ports
| Port | Service         |
|------|-----------------|
| 3000 | Next.js frontend |
| 8000 | FastAPI backend  |
| 5000 | MLflow UI        |
| 5432 | PostgreSQL       |
| 6379 | Redis            |
| 9000 | MinIO S3 API     |
| 9001 | MinIO Console    |
| 5555 | Flower (Celery)  |

---

## Build Progress (as of 2026-02-28)

### COMPLETED
- [x] Project scaffolding: `pyproject.toml`, `.env.example`, `Makefile`, `.pre-commit-config.yaml`
- [x] Docker Compose (8 services): postgres, redis, minio, minio-init, mlflow, api, worker, flower
- [x] `Dockerfile.api`, `Dockerfile.worker`, `docker-compose.override.yml`
- [x] `infra/postgres/init.sql`, `infra/minio/create_buckets.sh`
- [x] `src/core/config.py` — Pydantic Settings + `get_settings()` cache
- [x] `src/core/logging.py` — structlog (JSON prod / pretty dev)
- [x] `src/core/exceptions.py` — ForecastError, DataNotFoundError, ModelTrainingError, ReconciliationError, AgentError
- [x] `src/db/engine.py` — async SQLAlchemy engine + `get_db()` dependency
- [x] `src/db/models/` — Base, TimestampMixin, Restaurant, ProductGroup, SKU, DailySale, ForecastRun, ForecastValue, ModelAssignment
- [x] `src/db/migrations/` — Alembic async setup + `001_initial_schema.py`
- [x] `src/scripts/seed_synthetic.py` — 1 restaurant × 5 SKUs × 180 days, weekly/seasonal/holiday patterns, `np.random.seed(42)`
- [x] `src/ml/features/calendar.py` — DOW, month, Fourier (weekly + annual 3 harmonics), holiday flag
- [x] `src/ml/features/lag_features.py` — lag_7/14/28, rolling mean/std/min/max at 7/14/28
- [x] `src/ml/features/pipeline.py` — `build_feature_matrix()`, `get_feature_and_target()`, `build_future_frame()`
- [x] `src/ml/evaluation/metrics.py` — `mase()`, `smape()`, `wql()`, `coverage_80()`, `compute_all_metrics()`
- [x] `src/ml/models/base.py` — `BaseForecaster` ABC + `ForecastResult` dataclass
- [x] `src/ml/models/xgboost_model.py` — XGBoost wrapper, residual-std prediction intervals, feature importances
- [x] `src/ml/training/cross_validation.py` — `expanding_window_splits()` (4-fold expanding window)
- [x] `src/ml/training/trainer.py` — `train_single_series()` + `train_all_series()` with full MLflow logging, CV, final model, artifact registration

### NEXT — RESUME HERE
**Step 7: Celery app + forecast pipeline task**
Files to write:
- `src/workers/__init__.py`
- `src/workers/celery_app.py` — Celery instance, Redis broker/backend, beat schedule
- `src/workers/tasks/__init__.py`
- `src/workers/tasks/training.py` — `run_forecast_pipeline` task: loads sales from DB, calls `train_all_series()`, saves ForecastValue rows, updates ForecastRun status

**Step 8: FastAPI application**
Files to write:
- `src/api/__init__.py`
- `src/api/main.py` — FastAPI app, lifespan, middleware, routers
- `src/api/dependencies.py` — `get_db` re-export, common deps
- `src/api/schemas/forecasts.py` — ForecastRunCreate, ForecastRunRead, ForecastValueRead
- `src/api/schemas/restaurants.py` — RestaurantRead, SKURead
- `src/api/schemas/sales.py` — DailySaleRead
- `src/api/schemas/agents.py` — AgentEventRead (SSE payload)
- `src/api/routers/health.py` — GET /health
- `src/api/routers/restaurants.py` — GET /restaurants, GET /restaurants/{id}/skus
- `src/api/routers/sales.py` — GET /restaurants/{id}/sales
- `src/api/routers/forecasts.py` — POST /forecasts, GET /forecasts/{run_id}, GET /forecasts/{run_id}/values
- `src/api/routers/agents.py` — POST /agents/run, GET /agents/stream (SSE via sse-starlette)

**Step 9: Anthropic SDK orchestrator agent**
Files to write:
- `src/agents/__init__.py`
- `src/agents/orchestrator.py` — Manual tool use loop: claude-opus-4-6 + adaptive thinking + tool dispatch
- `src/agents/tools/__init__.py`
- `src/agents/tools/data_tools.py` — `get_sales_summary()`, `get_series_stats()`
- `src/agents/tools/model_tools.py` — `select_model()`, `suggest_hyperparams()`
- `src/agents/tools/mlflow_tools.py` — `get_best_run()`, `compare_runs()`
- `src/agents/tools/forecast_tools.py` — `trigger_forecast()`, `get_forecast_values()`

**Step 10: Next.js frontend**
- `frontend/Dockerfile.frontend`
- `frontend/package.json` + `next.config.ts` + `tsconfig.json`
- `frontend/src/app/layout.tsx` — root layout, nav
- `frontend/src/app/dashboard/page.tsx` — Recharts forecast chart + metrics cards
- `frontend/src/app/agents/page.tsx` — SSE event stream viewer
- `frontend/src/lib/api.ts` — typed fetch wrappers
- `frontend/src/types/api.ts` — auto-generated from Pydantic (or hand-written for now)

### Sprint 2 Backlog (not started)
- SARIMA, Prophet, LightGBM, LSTM, TFT models
- MinT hierarchical reconciliation
- Sub-agents (feature engineering agent, model selection agent, drift detection agent)
- Celery Beat drift detection schedule
- Optuna HPO integration
- pytest test suite (>70% coverage)
- TypeScript type auto-generation from Pydantic
