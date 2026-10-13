"""YouTube-only, deterministic heuristic. No AI estimates or cross-source ranking."""
from datetime import datetime, timezone
from math import log1p


def youtube_popularity(metrics, published_at, now=None):
    views = metrics.get("viewCount") if metrics else None
    if views is None or published_at is None:
        return None
    now = now or datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        return None
    age = (now - published_at).total_seconds() / 86400
    if age < -1:
        return None
    components = [(0.7, min(log1p(views / max(age, 1)) / log1p(100_000), 1))]
    for name, weight, ceiling in (("likeCount", 0.2, 0.10), ("commentCount", 0.1, 0.02)):
        count = metrics.get(name)
        if count is not None:
            components.append((weight, min(count / max(views, 1) / ceiling, 1)))
    return round(sum(weight * score for weight, score in components) / sum(weight for weight, _ in components), 6)
