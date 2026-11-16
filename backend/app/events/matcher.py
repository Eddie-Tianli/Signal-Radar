"""Hybrid Topic matching over normalized facts, with conservative semantic fallback."""
from sqlalchemy import select
from app.ai.provider import AIError
from app.events.models import TopicMatchRecord
from app.events.schemas import TopicMatchInput, TopicMatchResult
from app.events.identity import ALIASES, compact, entity_keys, family, digest, structured, direct_subject_action
from app.topics.policy import analysis_fingerprint, enabled_rules, rule_warnings

MATCHER_VERSION="1"


def match_fingerprint(topic):return digest({"policy":MATCHER_VERSION,"topic":analysis_fingerprint(topic)})


def literal_rule(text, prefix):
    for marker in prefix:
        if text.startswith(marker):return text[len(marker):].strip()
    return None


class TopicMatcher:
    def __init__(self,session,provider):self.session,self.provider=session,provider

    def match(self,topic,normalized,retry=False):
        fingerprint=match_fingerprint(topic)
        record=self.session.scalar(select(TopicMatchRecord).where(TopicMatchRecord.topic_id==topic.id,
            TopicMatchRecord.normalized_item_id==normalized.id,TopicMatchRecord.config_fingerprint==fingerprint))
        if record and record.processing_status=="completed" and (record.match_status!="uncertain" or not retry):return record
        includes,excludes=enabled_rules(topic,"include"),enabled_rules(topic,"exclude")
        data=structured(normalized)
        scope=compact(topic.name+" "+(topic.description or ""))
        text=compact(normalized.headline+" "+normalized.summary)
        result=None; ai_used=False
        # Only explicitly literal rules are hard string rules; natural language is semantic.
        for rule in excludes:
            term=literal_rule(rule,("排除关键词：","排除关键词:","禁止包含：","禁止包含:"))
            if term and compact(term) in text:
                result=TopicMatchResult(match_status="unmatched",relevance_score=0.0,matched_rules=[rule],exclusion_reason=rule,match_reason="命中明确的字面排除规则，优先于分数。")
                break
        for rule in includes:
            term=literal_rule(rule,("必须包含关键词：","必须包含关键词:"))
            if result is None and term and compact(term) not in text:
                result=TopicMatchResult(match_status="unmatched",relevance_score=0.0,matched_rules=[],exclusion_reason="",match_reason="未满足明确的字面包含条件。")
        if result is None and rule_warnings(topic):
            result=TopicMatchResult(match_status="uncertain",relevance_score=0.0,matched_rules=[],exclusion_reason="规则冲突",match_reason="；".join(rule_warnings(topic)))
        keys=entity_keys(normalized.entities)
        anchors={key for key in keys if key in scope or any(compact(alias) in scope for alias in ALIASES.get(key,()))}
        snapshot={"name":topic.name,"description":topic.description,"include_rules":includes,"exclude_rules":excludes,"threshold":topic.relevance_threshold,"subject_aliases":{k:list(ALIASES[k]) for k in anchors if k in ALIASES},"policy_version":MATCHER_VERSION}
        headline=compact(normalized.headline)
        # Require the subject in headline AND a factual clause, never just tag co-occurrence.
        linked=any(direct_subject_action(claim.get("text",""),ALIASES.get(key,(key,)))
                   for key in anchors for claim in (normalized.claims or []))
        headline_subject=any(any(alias in headline for alias in [key,*map(compact,ALIASES.get(key,()))]) for key in anchors)
        product_scope=compact(topic.description or "") in {compact(f"关注{topic.name}产品发布"),compact(f"收集{topic.name}模型发布信息")}
        broad_scope=not topic.description or compact(topic.description) in ("关注最新动态","关注相关动态")
        if result is None and not includes and not excludes and headline_subject and linked and (broad_scope or product_scope and family(normalized.event_type)=="product"):
            result=TopicMatchResult(match_status="matched",relevance_score=0.95,matched_rules=["subject","description"],exclusion_reason="",match_reason="标题和事实声称中主体直接参与该类事件；无额外语义限制。")
        if record is None:
            record=TopicMatchRecord(topic_id=topic.id,normalized_item_id=normalized.id,config_fingerprint=fingerprint,
                match_status="uncertain",relevance_score=0,matched_rules=[],exclusion_reason="",match_reason="待语义复核",ai_used=False,processing_status="failed")
            self.session.add(record)
        try:
            if result is None:
                ai_used=True
                result=self.provider.match_topic(TopicMatchInput(
                    topic=snapshot,normalized_item=data))
                result=TopicMatchResult.model_validate_json(result.model_dump_json()) if isinstance(result,TopicMatchResult) else TopicMatchResult.model_validate(result)
                allowed={"subject","description",*includes,*excludes}
                if not set(result.matched_rules)<=allowed:raise ValueError("Unknown rule reference")
            # A reason asserting definite exclusion is hard regardless of the AI score.
            if result.match_status!="uncertain" and result.exclusion_reason.strip():result.match_status="unmatched"
            if result.match_status=="matched" and result.relevance_score<topic.relevance_threshold:result.match_status="unmatched"
            identity_scope=" ".join([topic.description or "",*includes,*excludes]).casefold()
            if result.match_status=="matched" and any(term in identity_scope for term in ("官方","粉丝","个人发布","official source","fan account")):
                result.match_status="uncertain"
                result.match_reason="来源身份未核验，不能仅凭账号名满足身份限定。"
            for key,value in result.model_dump().items():setattr(record,key,value)
            record.processing_status,record.error="completed",None
        except Exception as error:
            record.match_status,record.match_reason="uncertain","语义核验未完成，不能自动通知。"
            record.processing_status,record.error="failed","Topic 匹配失败，请检查 Ollama 后重试。"
            record.topic_snapshot=snapshot
            record.ai_used=ai_used;self.session.commit()
            raise AIError(record.error,error.status_code if isinstance(error,AIError) else 502) from None
        record.topic_snapshot=snapshot
        record.ai_used=ai_used;self.session.commit()
        return record
