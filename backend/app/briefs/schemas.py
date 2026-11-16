from typing import Annotated
from pydantic import BaseModel,ConfigDict,Field,StringConstraints
Text=Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=1000)]


class BriefInput(BaseModel):
    event_id:int
    title:str
    entities:list[str]
    event_date:str|None
    facts:list[dict]
    sources:list[dict]
    coverage:str="limited_metadata"


class BriefResult(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
    title:Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=180)]
    summary:Text
    fact_indices:list[int]=Field(min_length=1,max_length=20)


class CompositionInput(BaseModel):
    topic:dict
    briefs:list[dict]


class EventParagraph(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
    brief_id:int
    text:Text


class CompositionResult(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
    title:Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=180)]
    core_updates:list[Text]=Field(min_length=1,max_length=5)
    events:list[EventParagraph]=Field(min_length=2,max_length=20)
    watch_points:list[Text]=Field(max_length=3)
