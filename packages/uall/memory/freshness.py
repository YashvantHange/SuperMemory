from datetime import datetime, timedelta

from uall_core.schemas.lesson import Lesson


def compute_staleness(lesson: Lesson) -> float:
    f = lesson.freshness
    if f.usage_count == 0:
        age_days = (datetime.utcnow() - f.created_at).days
        return min(0.5, age_days / 365)

    success_rate = f.success_after_use / max(f.usage_count, 1)
    staleness = 1.0 - success_rate

    if f.last_used:
        days_since = (datetime.utcnow() - f.last_used).days
        staleness += min(0.3, days_since / 180)

    if f.last_confirmed:
        days_since_confirm = (datetime.utcnow() - f.last_confirmed).days
        staleness -= min(0.2, days_since_confirm / 90)

    return round(max(0.0, min(1.0, staleness)), 4)


def freshness_weight(lesson: Lesson) -> float:
    lesson.freshness.staleness_score = compute_staleness(lesson)
    return 1.0 - lesson.freshness.staleness_score
