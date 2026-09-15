from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DigestItem(BaseModel):
    title: str
    source: str
    author: str | None
    published_at: datetime | None
    ai_category: str | None
    ai_relevance_score: float | None
    ai_summary: str | None


class DigestInput(BaseModel):
    topic_name: str
    topic_description: str | None
    items: list[DigestItem]


class DigestResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=5000)


class DigestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    topic_id: int
    title: str
    summary: str
    item_count: int
    generated_at: datetime
