from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.topics.schemas import Topic, TopicWrite, Rule, RuleWrite, RuleCreate
from app.topics.models import TopicRecord, TopicRuleRecord
from app.topics.service import TopicService, get_topic_service
from app.workflows.locks import topic_operation


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
    """Replace legacy fields; omitted intent rules/threshold preserve stored values."""
    with topic_operation(topic_id):
        topic = service.update_topic(topic_id, data)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: int, service: Service) -> Response:
    with topic_operation(topic_id):
        if not service.delete_topic(topic_id):
            raise HTTPException(status_code=404, detail="Topic not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{topic_id}/rules", response_model=Rule, status_code=201)
def add_rule(topic_id: int, data: RuleCreate, service: Service):
    with topic_operation(topic_id):
        topic = service.session.get(TopicRecord, topic_id)
        if topic is None:
            raise HTTPException(404, "Topic not found")
        if len(getattr(topic, data.rule_type + "_rules")) >= 10:
            raise HTTPException(422, "每类最多 10 条规则。")
        if data.id is not None:
            raise HTTPException(422, "新增规则不能指定 ID。")
        rule = TopicRuleRecord(topic_id=topic_id, **data.model_dump(exclude={"id"}))
        service.session.add(rule)
        service.session.commit()
        service.session.refresh(rule)
        return Rule.model_validate(rule)


@router.put("/{topic_id}/rules/{rule_id}", response_model=Rule)
def edit_rule(topic_id: int, rule_id: int, data: RuleWrite, service: Service):
    with topic_operation(topic_id):
        rule = service.session.get(TopicRuleRecord, rule_id)
        if rule is None or rule.topic_id != topic_id:
            raise HTTPException(404, "规则不存在。")
        if data.id is not None and data.id != rule_id:
            raise HTTPException(422, "规则 ID 不一致。")
        rule.text, rule.enabled = data.text, data.enabled
        service.session.commit()
        service.session.refresh(rule)
        return Rule.model_validate(rule)


@router.delete("/{topic_id}/rules/{rule_id}", status_code=204)
def delete_rule(topic_id: int, rule_id: int, service: Service):
    with topic_operation(topic_id):
        rule = service.session.get(TopicRuleRecord, rule_id)
        if rule is None or rule.topic_id != topic_id:
            raise HTTPException(404, "规则不存在。")
        service.session.delete(rule)
        service.session.commit()
        return Response(status_code=204)
