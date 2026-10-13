from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalysisInput(BaseModel):
    topic_name: str
    topic_description: str | None
    include_rules: list[str] = Field(default_factory=list)
    exclude_rules: list[str] = Field(default_factory=list)
    title: str
    snippet: str | None
    author: str | None
    source: str
    published_at: datetime | None = None
    collected_at: datetime | None = None
    analysis_time: datetime | None = None
    metadata_only: bool = True
    snippet_truncated: bool = False


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    # Kept for provider compatibility; never used by the deterministic validity policy.
    relevant: bool | None = None
    relevance_score: float = Field(ge=0, le=1, allow_inf_nan=False)
    relevance_reason: str = Field(min_length=1, max_length=800)
    exclusion_status: Literal["excluded", "not_excluded", "uncertain"]
    exclusion_reason: str = Field(max_length=800)
    category: str = Field(min_length=1, max_length=50)
    summary: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def exclusion_explanation(self):
        if self.exclusion_status != "not_excluded" and not self.exclusion_reason:
            raise ValueError("Excluded or uncertain content requires an explanation")
        return self


class BatchResult(BaseModel):
    topic_id: int
    processed: int = 0
    relevant: int = 0
    irrelevant: int = 0
    failed: int = 0
    review: int = 0
