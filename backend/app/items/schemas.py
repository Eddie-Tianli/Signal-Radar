from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ItemCreate(BaseModel):
    topic_id: int = Field(gt=0)
    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    external_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    title: NonEmptyString
    url: NonEmptyString
    author: str | None = None
    published_at: AwareDatetime | None = None
    snippet: str | None = None


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
