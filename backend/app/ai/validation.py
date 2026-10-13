"""Lightweight output guards, not a general fact verifier."""
import re


class AnalysisSemanticError(ValueError):
    pass


def validate_analysis(result, data):
    narrative = re.sub(r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’', "", result.summary)
    if re.search(r"(?i)\b(?:the user wants|the user is interested in|based on the provided|"
                 r"provided metadata|ignore previous instructions|i want you to)\b|"
                 r"用户(?:想要|希望)|根据\s*metadata|prompt\s*(?:说明|要求)", narrative):
        raise AnalysisSemanticError("Item summary contains task explanation or source instructions")
    if "```" in result.summary or re.search(r"<(?:think|system|assistant)(?:>|\s)", result.summary, re.I):
        raise AnalysisSemanticError("Code or role markup in Item summary")
    if not re.search(r"[\u4e00-\u9fff]", result.summary):
        raise AnalysisSemanticError("Item summary must use Chinese")
    context = data.topic_name + " " + (data.topic_description or "")
    if re.search(r"\bbeginner(?: level)?\s+c#\s+code\b", narrative, re.I) and "c#" not in context.casefold():
        raise AnalysisSemanticError("Unrelated code-writing summary")
    source = data.title + " " + (data.snippet or "")
    years = set(re.findall(r"(?<!\d)(?:19|20|21)\d{2}(?!\d)", source))
    if data.published_at is not None:
        years.add(str(data.published_at.year))
    if set(re.findall(r"(?<!\d)(?:19|20|21)\d{2}(?!\d)", result.summary)) - years:
        raise AnalysisSemanticError("Unsupported year in Item summary")
    return result
