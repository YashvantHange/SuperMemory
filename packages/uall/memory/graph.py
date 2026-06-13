from uall_core.schemas.graph import GraphEdgeType, KnowledgeGraph
from uall_core.schemas.lesson import Lesson


def get_lesson_graph(lesson: Lesson) -> KnowledgeGraph:
    if lesson.graph:
        return lesson.graph
    return KnowledgeGraph(lesson_id=lesson.lesson_id)


def add_edge(lesson: Lesson, edge_type: GraphEdgeType, target_id: str) -> Lesson:
    graph = get_lesson_graph(lesson)
    graph.add_edge(edge_type, target_id)
    lesson.graph = graph
    return lesson


def graph_to_dict(lesson: Lesson) -> dict:
    graph = get_lesson_graph(lesson)
    result: dict[str, list[str]] = {}
    for edge in graph.edges:
        key = edge.edge_type.value
        result.setdefault(key, []).append(edge.target_id)
    return {"lesson_id": lesson.lesson_id, "edges": result}
