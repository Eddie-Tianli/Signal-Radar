"""Small output guards, not fact checking or verification of source identity."""
import re
from datetime import date
from app.normalization.schemas import NormalizationResult


class NormalizationSemanticError(ValueError):
    pass


def validate_normalization(result: NormalizationResult, data):
    text = result.headline + "\n" + result.summary
    if not re.search(r"[\u4e00-\u9fff]", result.headline) or not re.search(r"[\u4e00-\u9fff]", result.summary):
        raise NormalizationSemanticError("Chinese headline and summary required")
    narrative = re.sub(r'"[^"\n]*"|“[^”\n]*”', "", text)
    if re.search(r"```|<(?:think|system|assistant)(?:>|\s)|<\|(?:system|assistant)|the user wants|based on the provided|ignore previous instructions|i want you to|作为(?:一个)?(?:AI|语言模型)", narrative, re.I):
        raise NormalizationSemanticError("Output contains task drift")
    # URLs and references are supplied by the program, never invented by the model.
    if re.search(r"https?://|www\.", text + " ".join(c.text for c in result.claims), re.I):
        raise NormalizationSemanticError("Model-generated source URL is not allowed")
    if re.search(r"(?<!未)(?<!未被)(?<!没有)(?:官方已(?:经)?证实|已(?:经)?核实|已(?:经)?证实|officially_confirmed)", text + " ".join(c.text for c in result.claims), re.I):
        raise NormalizationSemanticError("Verification not available in this pipeline")
    warnings = list(result.warnings)
    dates = set()
    for year, month, day in re.findall(r"((?:19|20|21)\d{2})[-/.年]\s*(\d{1,2})[-/.月]\s*(\d{1,2})(?!\d)", data.title + " " + data.text):
        try:
            dates.add(date(int(year), int(month), int(day)))
        except ValueError:
            warnings.append("资料含无效日期，尚未核验。")
    if len(dates) > 1:
        warnings.append("资料包含多个日期，可能是不同时间或冲突，尚未核验。")
    if result.event_date:
        value = result.event_date
        patterns = [rf"{value.year}[-/.年]\s*0?{value.month}[-/.月]\s*0?{value.day}(?!\d)",
                    rf"\b{value.day}\s+{value.strftime('%B')}\s+{value.year}\b",
                    rf"\b{value.strftime('%B')}\s+{value.day},?\s+{value.year}\b"]
        if not any(re.search(pattern, data.title + " " + data.text, re.I) for pattern in patterns):
            raise NormalizationSemanticError("Event date not supported by source text")
        if len(dates) > 1:
            result.event_date = None  # cannot choose one ambiguous event date
    years = set(re.findall(r"(?<!\d)(?:19|20|21)\d{2}(?!\d)", data.title + " " + data.text))
    if set(re.findall(r"(?<!\d)(?:19|20|21)\d{2}(?!\d)", text + " ".join(c.text for c in result.claims))) - years:
        raise NormalizationSemanticError("Unsupported year in brief")
    warnings.append("仅整理单一来源声称，未访问官方证据或交叉核验；reported 不代表已证实。")
    if data.content_coverage == "metadata_only":
        warnings.append("仅获得 YouTube 标题和 description，未读取完整视频或字幕。")
    else:
        warnings.append("仅依据已获得的标题与 snippet，内容完整性未知。")
    if data.text_truncated:
        warnings.append("本次模型输入按长度限制截取，原始 Item 完整保留。")
    result.warnings = list(dict.fromkeys(warnings))[:16]
    return result
