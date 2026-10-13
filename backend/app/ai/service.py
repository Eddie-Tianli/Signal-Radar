from datetime import datetime, timezone
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.ai.provider import AIError, AIProvider
from app.ai.validation import validate_analysis, AnalysisSemanticError
from app.ai.schemas import AnalysisInput, AnalysisResult, BatchResult
from app.items.models import ItemRecord
from app.items.schemas import Item
from app.topics.models import TopicRecord
from app.topics.policy import analysis_fingerprint, enabled_rules, final_status, pending_condition, rule_warnings


class AnalysisService:
    def __init__(self, session: Session, provider: AIProvider):
        self.session, self.provider = session, provider

    def pending_ids(self, topic, limit):
        return list(self.session.scalars(select(ItemRecord.id).where(
            ItemRecord.topic_id == topic.id, ItemRecord.deleted_at.is_(None), pending_condition(topic)
        ).order_by(ItemRecord.id).limit(limit)))

    def analyze(self, item_id: int) -> Item:
        item = self.session.get(ItemRecord, item_id)
        if item is None or item.deleted_at is not None:
            raise LookupError("Item not found")
        topic = item.topic
        fingerprint = analysis_fingerprint(topic)
        data = AnalysisInput(topic_name=topic.name[:200], topic_description=topic.description,
            include_rules=enabled_rules(topic, "include"), exclude_rules=enabled_rules(topic, "exclude"),
            published_at=(item.published_at.replace(tzinfo=timezone.utc) if item.published_at and item.published_at.tzinfo is None else item.published_at),
            collected_at=item.collected_at.replace(tzinfo=timezone.utc) if item.collected_at.tzinfo is None else item.collected_at,
            analysis_time=datetime.now(timezone.utc),
            title=item.title[:300], snippet=item.snippet[:2000] if item.snippet else None,
            snippet_truncated=bool(item.snippet and len(item.snippet) > 2000),
            author=item.author[:100] if item.author else None, source=item.source)
        try:
            result = validate_analysis(AnalysisResult.model_validate(self.provider.analyze(data)), data)
        except (AIError, ValidationError, AnalysisSemanticError) as error:
            # Failed attempts never become invalid, and previous raw/AI content is retained.
            item.analysis_status = "failed"
            # Keep the fingerprint of the last successful result; a failed attempt
            # must not make an old summary look current under changed rules.
            item.analysis_error = "分析未完成，请检查 Ollama 或 Trace 后重试。"
            if isinstance(error, AnalysisSemanticError) or "unsupported facts" in str(error):
                item.analysis_error = "AI 摘要未通过事实、语言或指令安全校验，请核对来源后重新分析。"
            elif "input is too long" in str(error):
                item.analysis_error = "AI 输入过长，请缩短主题描述或启用的规则后重试。"
            elif isinstance(error, ValidationError) or "invalid structured" in str(error):
                item.analysis_error = "AI 返回的数据格式不符合要求，请重新分析或查看 Trace。"
            elif isinstance(error, AIError) and error.status_code == 504:
                item.analysis_error = "Ollama 分析超时，请稍后重试。"
            elif isinstance(error, AIError) and error.status_code == 503:
                item.analysis_error = "Ollama 服务或模型不可用，请检查本地服务与配置。"
            item.ai_relevant = False
            self.session.commit()
            if isinstance(error, AIError):
                raise
            if isinstance(error, AnalysisSemanticError):
                raise AIError("AI summary contains unsupported facts. Check source metadata and retry.") from None
            raise AIError("Ollama returned invalid structured analysis. Retry or check model support.") from None
        item.analysis_status = final_status(topic, result)
        item.analysis_fingerprint = fingerprint
        item.analysis_error = None
        item.ai_relevant = item.analysis_status == "valid"
        item.ai_relevance_score = result.relevance_score
        item.relevance_reason = result.relevance_reason
        item.exclusion_status = "uncertain" if rule_warnings(topic) else result.exclusion_status
        item.exclusion_reason = "；".join(rule_warnings(topic)) or result.exclusion_reason
        item.ai_category, item.ai_summary = result.category, result.summary
        item.ai_analyzed_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(item)
        return Item.model_validate(item)

    def analyze_topic(self, topic_id: int, limit: int) -> BatchResult:
        topic = self.session.get(TopicRecord, topic_id)
        if topic is None:
            raise LookupError("Topic not found")
        result = BatchResult(topic_id=topic_id)
        for item_id in self.pending_ids(topic, limit):
            try:
                item = self.analyze(item_id)
                result.processed += 1
                result.relevant += int(item.analysis_status == "valid")
                result.irrelevant += int(item.analysis_status == "invalid")
                result.review += int(item.analysis_status == "review")
            except AIError:
                self.session.rollback()
                result.failed += 1
        return result
