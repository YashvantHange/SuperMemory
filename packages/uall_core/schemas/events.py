from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

MAX_PAYLOAD_BYTES = 2048


class EventType(str, Enum):
    WORKFLOW_START = "workflow_start"
    WORKFLOW_STEP = "workflow_step"
    WORKFLOW_END = "workflow_end"
    FAILURE = "failure"
    CORRECTION = "correction"
    SUGGESTION = "suggestion"
    TOOL_OUTCOME = "tool_outcome"


class StageMetadata(BaseModel):
    workflow: str | None = None
    step: str | None = None
    tool: str | None = None
    agent: str | None = None
    domain: str | None = None
    language: str | None = None
    environment: str | None = None
    namespace: str | None = None
    namespace_id: str | None = None


class Event(BaseModel):
    event_id: str
    event_type: EventType
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    stage: StageMetadata = Field(default_factory=StageMetadata)
    tags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def validate_payload_size(cls, v: dict) -> dict:
        import json

        if len(json.dumps(v, default=str)) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"Payload exceeds {MAX_PAYLOAD_BYTES} bytes")
        return v


class RunStart(BaseModel):
    run_id: str
    workflow_id: str
    agents: list[str] = Field(default_factory=list)
    workflow_graph: dict[str, Any] = Field(default_factory=dict)
    stage: StageMetadata = Field(default_factory=StageMetadata)


class RunEnd(BaseModel):
    run_id: str
    success: bool
    metrics: dict[str, Any] = Field(default_factory=dict)
    lessons_used: list[str] = Field(default_factory=list)
    score: float | None = None


class Feedback(BaseModel):
    run_id: str | None = None
    lesson_id: str | None = None
    rating: str  # positive, negative, correction
    comment: str | None = None
    correction_before: str | None = None
    correction_after: str | None = None
    intent: str | None = None
