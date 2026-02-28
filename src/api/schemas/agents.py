from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AgentEventType(str, enum.Enum):
    thinking = "thinking"
    tool_call = "tool_call"
    tool_result = "tool_result"
    message = "message"
    error = "error"
    done = "done"


class AgentRunCreate(BaseModel):
    prompt: str
    model: str = "claude-opus-4-6"


class AgentRunRead(BaseModel):
    stream_id: str


class AgentEventRead(BaseModel):
    event_type: AgentEventType
    stream_id: str
    data: dict[str, Any]
    timestamp: datetime
