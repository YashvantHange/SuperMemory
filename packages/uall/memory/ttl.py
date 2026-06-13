from datetime import datetime, timedelta

from uall_core.schemas.lesson import Lesson


def is_expired(lesson: Lesson) -> bool:
    if lesson.ttl.expires_at and lesson.ttl.expires_at < datetime.utcnow():
        return True
    if lesson.ttl.auto_revalidate_after_days:
        cutoff = lesson.freshness.created_at + timedelta(days=lesson.ttl.auto_revalidate_after_days)
        if datetime.utcnow() > cutoff and not lesson.freshness.last_confirmed:
            lesson.status = "pending_revalidation"
            return True
    return False


def ttl_weight(lesson: Lesson) -> float:
    if is_expired(lesson):
        return 0.0
    if lesson.status == "pending_revalidation":
        return 0.1
    return 1.0
