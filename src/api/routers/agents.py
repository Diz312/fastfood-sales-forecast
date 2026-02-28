"""SSE agent streaming endpoint."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies import get_db
from src.api.schemas.agents import AgentRunCreate, AgentRunRead

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run", response_model=AgentRunRead, status_code=201)
async def start_agent_run(
    body: AgentRunCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from src.agents.orchestrator import run_orchestrator

    stream_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    request.app.state.agent_streams[stream_id] = queue

    asyncio.create_task(
        run_orchestrator(
            prompt=body.prompt,
            stream_id=stream_id,
            queue=queue,
            db=db,
        )
    )

    return {"stream_id": stream_id}


@router.get("/stream/{stream_id}")
async def agent_stream(stream_id: str, request: Request) -> EventSourceResponse:
    queue: asyncio.Queue | None = request.app.state.agent_streams.get(stream_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    async def generator():  # type: ignore[return]
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
                    continue

                yield {
                    "event": event["event_type"],
                    "data": json.dumps(event["data"]),
                }

                if event["event_type"] in ("done", "error"):
                    break
        finally:
            request.app.state.agent_streams.pop(stream_id, None)

    return EventSourceResponse(generator())
