import re

from app.digests.schemas import DigestInput, DigestResult


class DigestSemanticError(ValueError):
    """A structured result fails the local brief safety checks."""


def validate_digest(result: DigestResult, data: DigestInput) -> None:
    # These are conservative output checks, not a proof of factual relevance.
    text = result.title + "\n" + result.summary
    forbidden = (
        r"\bi want you to\b", r"\bthe user (?:wants|is interested in)\b",
        r"\bignore (?:all )?(?:previous|prior) instructions\b", r"\bwrite a story\b",
        r"\b(?:provided metadata|based on the provided|provided items)\b",
        r"根据提供的信息", r"(?:仅|只)(?:需|要)?(?:输出|返回)\s*(?:合法\s*)?JSON",
        r"\breturn only (?:the result )?json\b", r"\b(?:summary|title)\s*(?:长度|字数|字段|符合)",
        r"\bai_relevance_score\s*(?:为|是|=|:|：)", r"仅(?:组织|总结|合并)(?:已)?(?:提供|给定)", r"(?:匹配|符合)(?:此|该)\s*schema", r"忽略(?:之前|以前|上述|所有).*指令",
        r"<(?:think|system|assistant)(?:>|\s)", r"```",
    )
    # Reports may legitimately quote attack phrases; inspect narrative, not quotations.
    narrative = re.sub(r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’', "", text)
    if any(re.search(pattern, narrative, re.I) for pattern in forbidden):
        raise DigestSemanticError("Instruction-following or malformed output")
    if all(re.search(pattern, text) for pattern in (r'"additionalProperties"\s*:', r'"properties"\s*:', r'"required"\s*:')):
        raise DigestSemanticError("Schema definition echoed into brief")
    context = data.topic_name + " " + (data.topic_description or "")
    if re.search(r"\bbeginner(?: level)?\s+c#\s+code\b", narrative, re.I) and "c#" not in context.lower():
        raise DigestSemanticError("Unrelated code-writing output")
    for index, value in enumerate((result.title, result.summary)):
        han = len(re.findall(r"[\u4e00-\u9fff]", value))
        latin = len(re.findall(r"[a-zA-Z]", value))
        kana = len(re.findall(r"[\u3040-\u30ff]", value))
        # Short titles may legitimately contain long English product names.
        if not value.strip() or han == 0 or (index == 1 and han * 3 < latin) or kana > han:
            raise DigestSemanticError("Brief must primarily use Chinese")
    allowed = {item.unit_id for item in data.items if item.unit_id}
    if any(f"U{number}" not in allowed for number in re.findall(r"\[U(\d+)\]", result.summary, re.I)):
        raise DigestSemanticError("Unknown source unit citation")
    allowed_urls = {ref.url for item in data.items for ref in item.source_refs}
    for item in data.items:
        allowed_urls.update(url.rstrip(".,，。；;)") for url in re.findall(r"https?://[^\s<>\"']+", (item.title + "\n" + (item.ai_summary or ""))))
    urls = {url.rstrip(".,，。；;)") for url in re.findall(r"https?://[^\s<>\"']+", result.summary)}
    if urls - allowed_urls:
        raise DigestSemanticError("Unprovided source URL in brief")
    # Require an explicit Topic anchor, rather than accepting a fluent unrelated brief.
    anchors = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]*|[\u4e00-\u9fff]+", data.topic_name)
    anchors = [word for word in anchors if len(word) >= 2]
    # The deterministic query template also uses this well-defined cross-language entity.
    if "诺兰" in data.topic_name or re.search(r"\bnolan\b", data.topic_name, re.I):
        anchors.extend(["诺兰", "Nolan"])
    if anchors and not any(
        re.search(r"(?<![a-zA-Z0-9])" + re.escape(word) + r"(?![a-zA-Z0-9])", text, re.I)
        if word.isascii() else word in text for word in anchors
    ):
        raise DigestSemanticError("Brief lacks a Topic anchor")
