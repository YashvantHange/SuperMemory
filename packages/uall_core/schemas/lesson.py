from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from uall_core.schemas.events import StageMetadata
from uall_core.schemas.graph import KnowledgeGraph
from uall_core.schemas.namespace import (
    ConfidenceDimensions,
    FreshnessMetrics,
    MemoryType,
    NamespaceRef,
    Provenance,
    TTLConfig,
)


class Reflection(BaseModel):
    reflection_id: str
    failure: str
    root_cause: str
    fix: str
    confidence: float = 0.8
    memory_type: MemoryType = MemoryType.FAILURE
    run_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Lesson(BaseModel):
    lesson_id: str
    failure: str = ""
    root_cause: str = ""
    fix: str = ""
    memory_type: MemoryType = MemoryType.FAILURE
    stage: StageMetadata = Field(default_factory=StageMetadata)
    namespace: NamespaceRef = Field(default_factory=NamespaceRef)
    confidence: ConfidenceDimensions = Field(default_factory=ConfidenceDimensions)
    freshness: FreshnessMetrics = Field(default_factory=FreshnessMetrics)
    ttl: TTLConfig = Field(default_factory=TTLConfig)
    provenance: Provenance = Field(default_factory=Provenance)
    graph: KnowledgeGraph | None = None
    occurrence_count: int = 1
    quality_score: float = 0.5
    embedding: list[float] | None = None
    status: str = "active"  # active, archived, pending_revalidation
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_search_text(self) -> str:
        return f"{self.failure} {self.root_cause} {self.fix}"


class CandidateLesson(BaseModel):
    """Pre-validation lesson from reflection/distillation."""
    reflection_id: str
    failure: str
    root_cause: str
    fix: str
    memory_type: MemoryType = MemoryType.FAILURE
    stage: StageMetadata = Field(default_factory=StageMetadata)
    namespace: NamespaceRef = Field(default_factory=NamespaceRef)
    confidence: float = 0.8
    run_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)
    evidence_payload: dict = Field(default_factory=dict)


class MemorySearchRequest(BaseModel):
    query: str
    workflow: str | None = None
    step: str | None = None
    tool: str | None = None
    agent: str | None = None
    domain: str | None = None
    namespace: str | None = None
    namespace_id: str | None = None
    max_tokens: int = 800
    top_k: int = 5


class MemorySearchResult(BaseModel):
    lesson: Lesson
    score: float
    telemetry_id: str | None = None


class ValidatorAction(str):
    REJECT = "reject"
    MERGE = "merge"
    REWRITE = "rewrite"
    APPROVE = "approve"


class ValidationResult(BaseModel):
    action: str
    candidate: CandidateLesson
    quality_score: float = 0.0
    merge_target_id: str | None = None
    rewritten_fix: str | None = None
    reason: str = ""


class PendingLesson(BaseModel):
    pending_id: str
    candidate: CandidateLesson
    validation_result: ValidationResult
    status: str = "pending"  # pending, evaluating, promoted, discarded
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: datetime | None = None
