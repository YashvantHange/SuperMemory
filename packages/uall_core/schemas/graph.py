from enum import Enum

from pydantic import BaseModel, Field


class GraphEdgeType(str, Enum):
    CAUSED_BY = "caused_by"
    FIXED_BY = "fixed_by"
    SUPERSEDES = "supersedes"
    RELATED_TO = "related_to"
    DEPENDS_ON = "depends_on"
    CONFLICTS_WITH = "conflicts_with"
    DERIVED_FROM = "derived_from"
    GENERALIZES = "generalizes"
    SPECIALIZES = "specializes"


class GraphEdge(BaseModel):
    edge_type: GraphEdgeType
    target_id: str


class KnowledgeGraph(BaseModel):
    lesson_id: str
    edges: list[GraphEdge] = Field(default_factory=list)

    def get_targets(self, edge_type: GraphEdgeType) -> list[str]:
        return [e.target_id for e in self.edges if e.edge_type == edge_type]

    def add_edge(self, edge_type: GraphEdgeType, target_id: str) -> None:
        if not any(e.edge_type == edge_type and e.target_id == target_id for e in self.edges):
            self.edges.append(GraphEdge(edge_type=edge_type, target_id=target_id))
