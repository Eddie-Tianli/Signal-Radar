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
        r"根据提供的信息", r"忽略(?:之前|以前|上述|所有).*指令",
        r"<(?:think|system|assistant)(?:>|\s)", r"```",
    )
    # Reports may legitimately quote attack phrases; inspect narrative, not quotations.
    narrative = re.sub(r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’', "", text)
    if any(re.search(pattern, narrative, re.I) for pattern in forbidden):
        raise DigestSemanticError("Instruction-following or malformed output")
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
    # Require an explicit Topic anchor, rather than accepting a fluent unrelated brief.
    anchors = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]*|[\u4e00-\u9fff]+", data.topic_name)
    anchors = [word for word in anchors if len(word) >= 2]
    if anchors and not any(
        re.search(r"(?<![a-zA-Z0-9])" + re.escape(word) + r"(?![a-zA-Z0-9])", text, re.I)
        if word.isascii() else word in text for word in anchors
    ):
        raise DigestSemanticError("Brief lacks a Topic anchor")
