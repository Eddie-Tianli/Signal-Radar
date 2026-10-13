from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class RuleWrite(BaseModel):
    text: Text
    enabled: bool = True
    id: int | None = Field(default=None, gt=0)


class RuleCreate(RuleWrite):
    rule_type: Literal["include", "exclude"]


class Rule(RuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    topic_id: int


class TopicWrite(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool = True
    relevance_threshold: float = Field(default=0.80, ge=0, le=1, allow_inf_nan=False)
    include_rules: list[RuleWrite] | None = Field(default=None, max_length=10)
    exclude_rules: list[RuleWrite] | None = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def unique_rule_ids(self):
        ids = [rule.id for rule in (self.include_rules or []) + (self.exclude_rules or []) if rule.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate rule IDs")
        return self


class Topic(TopicWrite):
    model_config = ConfigDict(from_attributes=True)
    # Reading legacy names/descriptions must not apply new write-length limits.
    name: str
    description: str | None = None
    id: int
    include_rules: list[Rule] = Field(default_factory=list)
    exclude_rules: list[Rule] = Field(default_factory=list)
    rule_warnings: list[str] = Field(default_factory=list)
    last_queries: list[str] | None = None
    last_scan_at: datetime | None = None
