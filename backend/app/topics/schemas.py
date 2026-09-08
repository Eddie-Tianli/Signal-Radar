from typing import Annotated

from pydantic import BaseModel, StringConstraints


class TopicWrite(BaseModel):
    """Fields for creating or fully replacing a topic."""

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    description: str | None = None
    enabled: bool = True


class Topic(TopicWrite):
    id: int
