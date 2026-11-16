from datetime import date, datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SCHEMA_VERSION = "1"
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
    # No officially_confirmed: this pipeline has no evidence-verification capability.
    status: Literal["reported", "unconfirmed", "conflicting", "unknown"]


class NormalizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    headline: Text
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    entities: list[Text] = Field(max_length=20)
    event_type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    event_date: date | None
    keywords: list[Text] = Field(max_length=15)
    claims: list[Claim] = Field(max_length=12)
    warnings: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]] = Field(max_length=12)


class NormalizationInput(BaseModel):
    item_id: int
    title: str
    text: str
    source: str
    author: str | None
    published_at: datetime | None
    url: str
    content_coverage: Literal["metadata_only", "snippet_only"]
    text_truncated: bool
    source_metadata: dict


class SourceReference(BaseModel):
    item_id: int
    url: str
    source: str
    author: str | None
    published_at: datetime | None


class NormalizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_id: int
    schema_version: str
    revision: int
    input_fingerprint: str
    normalization_status: Literal["processing", "completed", "failed"]
    headline: str | None
    summary: str | None
    entities: list[str] | None
    event_type: str | None
    event_date: date | None
    keywords: list[str] | None
    claims: list[Claim] | None
    warnings: list[str]
    source_reference: SourceReference
    content_coverage: str
    text_truncated: bool
    source_metadata: dict
    matching_text: str
    model_name: str
    normalized_at: datetime | None
    error: str | None


class NormalizationBatch(BaseModel):
    topic_id: int
    processed: int = 0
    failed: int = 0
    reused: int = 0
