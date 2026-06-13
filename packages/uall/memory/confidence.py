from uall_core.schemas.lesson import Lesson
from uall_core.schemas.namespace import ConfidenceDimensions


def recalculate_overall(confidence: ConfidenceDimensions) -> float:
    return confidence.recalculate_overall()


def update_from_telemetry(
    lesson: Lesson, used: bool, accepted: bool, improved: bool | None
) -> Lesson:
    if used:
        lesson.freshness.usage_count += 1
        from datetime import datetime

        lesson.freshness.last_used = datetime.utcnow()
    if improved is True:
        lesson.freshness.success_after_use += 1
        lesson.confidence.retrieval_success = min(1.0, lesson.confidence.retrieval_success + 0.01)
    elif improved is False:
        lesson.freshness.failure_after_use += 1
        lesson.confidence.retrieval_success = max(0.0, lesson.confidence.retrieval_success - 0.03)
    if accepted:
        lesson.confidence.human_verified = True
        from datetime import datetime

        lesson.freshness.last_confirmed = datetime.utcnow()
    lesson.confidence.recalculate_overall()
    return lesson


def update_from_human_confirmation(lesson: Lesson) -> Lesson:
    lesson.confidence.human_verified = True
    lesson.confidence.evidence = min(1.0, lesson.confidence.evidence + 0.05)
    lesson.confidence.recalculate_overall()
    return lesson
