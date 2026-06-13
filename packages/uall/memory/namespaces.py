from uall_core.schemas.namespace import NAMESPACE_PRIORITY, NamespaceLevel, NamespaceRef


def parse_namespace(namespace: str | None) -> NamespaceRef | None:
    if not namespace:
        return None
    if ":" in namespace:
        level_str, ns_id = namespace.split(":", 1)
        try:
            level = NamespaceLevel(level_str)
        except ValueError:
            level = NamespaceLevel.PROJECT
        return NamespaceRef(level=level, namespace_id=ns_id)
    return NamespaceRef(namespace_id=namespace)


def namespace_match_score(lesson_ns: NamespaceRef, query_ns: NamespaceRef | None) -> float:
    if query_ns is None:
        return 0.5
    if lesson_ns.namespace_id == query_ns.namespace_id and lesson_ns.level == query_ns.level:
        return 1.0
    try:
        lesson_pri = NAMESPACE_PRIORITY.index(lesson_ns.level)
        query_pri = NAMESPACE_PRIORITY.index(query_ns.level)
        if lesson_pri <= query_pri:
            return 0.7
    except ValueError:
        pass
    return 0.3


RETRIEVAL_PRIORITY = [
    "policies",
    NamespaceLevel.ORGANIZATION,
    NamespaceLevel.TEAM,
    NamespaceLevel.PROJECT,
    NamespaceLevel.USER,
    NamespaceLevel.SESSION,
    NamespaceLevel.GLOBAL,
]
