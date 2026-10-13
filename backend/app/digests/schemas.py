from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DigestSource(BaseModel):
    item_id: int
    unit_id: str
    title: str
    source: str
    url: str
    author: str | None = None
    published_at: datetime | None = None


class DigestItem(BaseModel):
    title: str
    source: str
    author: str | None
    published_at: datetime | None
    ai_category: str | None
    ai_relevance_score: float | None
    ai_summary: str | None
    unit_id: str | None = None
    item_ids: list[int] = Field(default_factory=list)
    source_refs: list[DigestSource] = Field(default_factory=list)


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
    sources: list[DigestSource] | None = None
