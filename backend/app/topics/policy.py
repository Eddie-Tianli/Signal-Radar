"""One deterministic validity policy for every analysis entry point."""
import hashlib
import json
import re
from sqlalchemy import or_
from app.items.models import ItemRecord


def enabled_rules(topic, kind):
    return [rule.text for rule in topic.rules if rule.enabled and rule.rule_type == kind]


def rule_warnings(topic):
    normalize = lambda value: re.sub(r"\s+", "", value).casefold()
    includes = {normalize(text) for text in enabled_rules(topic, "include")}
    excludes = {normalize(text) for text in enabled_rules(topic, "exclude")}
    return ["包含与排除条件存在相同文本，请澄清规则；当前分析将进入待复核。"] if includes & excludes else []


def analysis_fingerprint(topic):
    payload = {"policy": "v0.2.0-1", "name": topic.name, "description": topic.description,
               "threshold": topic.relevance_threshold if topic.relevance_threshold is not None else 0.80,
               "include": sorted(enabled_rules(topic, "include")), "exclude": sorted(enabled_rules(topic, "exclude"))}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def pending_condition(topic):
    return or_(ItemRecord.analysis_fingerprint.is_(None),
               ItemRecord.analysis_fingerprint != analysis_fingerprint(topic),
               ItemRecord.analysis_status.in_(["pending", "failed"]))


def final_status(topic, result):
    if rule_warnings(topic) or result.exclusion_status == "uncertain":
        return "review"
    if result.exclusion_status == "excluded" or result.relevance_score < topic.relevance_threshold:
        return "invalid"
    return "valid"
