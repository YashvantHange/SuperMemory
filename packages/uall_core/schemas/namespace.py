from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    USER = "user"
    ORGANIZATIONAL = "organizational"
    FAILURE = "failure"
    TOOL = "tool"


class NamespaceLevel(str, Enum):
    GLOBAL = "global"
    ORGANIZATION = "organization"
    TEAM = "team"
    PROJECT = "project"
    USER = "user"
    SESSION = "session"


NAMESPACE_PRIORITY = [
    NamespaceLevel.ORGANIZATION,
    NamespaceLevel.TEAM,
    NamespaceLevel.PROJECT,
    NamespaceLevel.USER,
    NamespaceLevel.SESSION,
    NamespaceLevel.GLOBAL,
]


class NamespaceRef(BaseModel):
    level: NamespaceLevel = NamespaceLevel.PROJECT
    namespace_id: str = "default"


class ConfidenceDimensions(BaseModel):
    evidence: float = 0.5
    retrieval_success: float = 0.5
    human_verified: bool = False
    overall: float = 0.5

    def recalculate_overall(self) -> float:
        bonus = 1.0 if self.human_verified else 0.0
        self.overall = round(
            0.4 * self.evidence + 0.4 * self.retrieval_success + 0.2 * bonus, 4
        )
        return self.overall


class TTLConfig(BaseModel):
    expires_at: datetime | None = None
    auto_revalidate_after_days: int | None = None


class FreshnessMetrics(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: datetime | None = None
    last_confirmed: datetime | None = None
    usage_count: int = 0
    success_after_use: int = 0
    failure_after_use: int = 0
    staleness_score: float = 0.0


class Provenance(BaseModel):
    run_id: str | None = None
    reflection_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)
    policy_version: str | None = None
    validator_action: str | None = None
    promoted_at: datetime | None = None
