from pydantic import BaseModel, ConfigDict, Field


class AnalysisInput(BaseModel):
    topic_name: str
    topic_description: str | None
    title: str
    snippet: str | None
    author: str | None
    source: str


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    relevant: bool
    relevance_score: float = Field(ge=0, le=1, allow_inf_nan=False)
    category: str = Field(min_length=1, max_length=50)
    summary: str = Field(min_length=1, max_length=1000, description="A short summary in 1-3 sentences")


class BatchResult(BaseModel):
    topic_id: int
    processed: int = 0
    relevant: int = 0
    irrelevant: int = 0
    failed: int = 0
