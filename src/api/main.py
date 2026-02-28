from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import agents, forecasts, health, restaurants, sales
from src.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    app.state.agent_streams: dict[str, Any] = {}
    yield
    app.state.agent_streams.clear()


app = FastAPI(
    title="Fast Food Sales Forecast API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(restaurants.router, prefix="/restaurants", tags=["restaurants"])
app.include_router(sales.router, prefix="/restaurants", tags=["sales"])
app.include_router(forecasts.router, prefix="/forecasts", tags=["forecasts"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
