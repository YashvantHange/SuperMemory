from uall_core.schemas.lesson import Lesson
from uall_core.schemas.namespace import Provenance


def attach_provenance(
    lesson: Lesson,
    run_id: str | None = None,
    reflection_id: str | None = None,
    event_ids: list[str] | None = None,
    policy_version: str | None = None,
    validator_action: str | None = None,
) -> Lesson:
    from datetime import datetime

    lesson.provenance = Provenance(
        run_id=run_id or lesson.provenance.run_id,
        reflection_id=reflection_id or lesson.provenance.reflection_id,
        event_ids=event_ids or lesson.provenance.event_ids,
        policy_version=policy_version or lesson.provenance.policy_version,
        validator_action=validator_action or lesson.provenance.validator_action,
        promoted_at=datetime.utcnow(),
    )
    return lesson
