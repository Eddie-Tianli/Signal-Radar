from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.topics.schemas import Topic, TopicWrite
from app.topics.service import TopicService, get_topic_service


router = APIRouter(prefix="/api/topics", tags=["Topics"])
Service = Annotated[TopicService, Depends(get_topic_service)]


@router.get("", response_model=list[Topic])
def list_topics(service: Service) -> list[Topic]:
    return service.list_topics()


@router.get("/{topic_id}", response_model=Topic)
def get_topic(topic_id: int, service: Service) -> Topic:
    topic = service.get_topic(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.post("", response_model=Topic, status_code=status.HTTP_201_CREATED)
def create_topic(data: TopicWrite, service: Service) -> Topic:
    return service.create_topic(data)


@router.put("/{topic_id}", response_model=Topic)
def update_topic(topic_id: int, data: TopicWrite, service: Service) -> Topic:
    """Replace all editable fields; omitted optional fields use their defaults."""
    topic = service.update_topic(topic_id, data)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: int, service: Service) -> Response:
    if not service.delete_topic(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
