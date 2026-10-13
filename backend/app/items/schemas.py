from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class NormalizedItem(BaseModel):
    """Source-independent content, before association with a local Topic."""
    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    external_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    title: NonEmptyString
    url: NonEmptyString
    author: str | None = None
    published_at: AwareDatetime | None = None
    snippet: str | None = None
    popularity_score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    popularity_metrics: dict | None = None


class ItemCreate(NormalizedItem):
    topic_id: int = Field(gt=0)


class Item(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    source: str
    external_id: str
    title: str
    url: str
    author: str | None
    published_at: datetime | None
    snippet: str | None
    collected_at: datetime
    ai_relevant: bool | None = None
    ai_relevance_score: float | None = None
    ai_category: str | None = None
    ai_summary: str | None = None
    ai_analyzed_at: datetime | None = None

    analysis_status: str = "pending"
    analysis_stale: bool = False
    analysis_fingerprint: str | None = None
    relevance_reason: str | None = None
    exclusion_status: str | None = None
    exclusion_reason: str | None = None
    analysis_error: str | None = None
    popularity_score: float | None = None
    popularity_metrics: dict | None = None

    @model_validator(mode="before")
    @classmethod
    def current_status(cls, value):
        if hasattr(value, "topic"):
            from app.topics.policy import analysis_fingerprint
            data = {name: getattr(value, name, field.default) for name, field in cls.model_fields.items() if name != "analysis_stale"}
            stale = value.analysis_fingerprint != analysis_fingerprint(value.topic)
            data["analysis_stale"] = stale and value.ai_analyzed_at is not None
            if stale and value.analysis_status != "failed":
                data["analysis_status"] = "pending"
            return data
        return value
