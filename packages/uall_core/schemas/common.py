from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PolicyVersion(BaseModel):
    policy_id: str
    version: str
    effective_at: datetime = Field(default_factory=datetime.utcnow)
    rules: list[str] = Field(default_factory=list)
    priority: int = 100


class Skill(BaseModel):
    skill_id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    steps: list[str] = Field(default_factory=list)
    lesson_ids: list[str] = Field(default_factory=list)
    tool_bindings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExperimentMetrics(BaseModel):
    success_rate: float = 0.0
    retry_count: float = 0.0
    cost: float = 0.0
    correction_rate: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    token_usage: float = 0.0
    human_approval_rate: float = 0.0
    rollback_frequency: float = 0.0
    downstream_failure_rate: float = 0.0
    sample_size: int = 0


class Experiment(BaseModel):
    experiment_id: str
    resource_type: str  # prompt, workflow
    resource_id: str
    variant_a: str
    variant_b: str
    traffic_split: float = 0.1
    status: str = "running"  # running, concluded, rolled_back
    metrics_a: ExperimentMetrics = Field(default_factory=ExperimentMetrics)
    metrics_b: ExperimentMetrics = Field(default_factory=ExperimentMetrics)
    winner: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    concluded_at: datetime | None = None


class RetrievalTelemetryEvent(BaseModel):
    telemetry_id: str
    lesson_id: str
    run_id: str | None = None
    retrieved: bool = True
    used: bool = False
    accepted: bool = False
    outcome_improved: bool | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class VersionRecord(BaseModel):
    resource_type: str
    resource_id: str
    version: str
    content: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    promoted: bool = False
