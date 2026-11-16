from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
Text = Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=1000)]


class TopicMatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid",strict=True)
    match_status: Literal["matched","unmatched","uncertain"]
    relevance_score: float = Field(ge=0,le=1,allow_inf_nan=False)
    matched_rules: list[str] = Field(max_length=20)
    exclusion_reason: str = Field(max_length=1000)
    match_reason: Text


class TopicMatchInput(BaseModel):
    topic: dict
    normalized_item: dict


class EventRelationResult(BaseModel):
    model_config = ConfigDict(extra="forbid",strict=True)
    relation: Literal["new_event","duplicate_report","event_update","uncertain"]
    confidence: float = Field(ge=0,le=1,allow_inf_nan=False)
    reason: Text
    new_fact_indices: list[int] = Field(max_length=12)
    conflicting_fact_indices: list[int] = Field(max_length=12)
    importance: float = Field(ge=0,le=1,allow_inf_nan=False)


class EventRelationInput(BaseModel):
    incoming: dict
    candidate: dict
