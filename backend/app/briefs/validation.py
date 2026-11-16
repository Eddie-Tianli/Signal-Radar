import re
from app.events.identity import compact,ALIASES


class ReadingValidationError(ValueError):pass


def _grounded(text,context,entities):
    if not re.search(r"[\u4e00-\u9fff]",text) or len(re.findall(r"[a-zA-Z]",text))>3*len(re.findall(r"[\u4e00-\u9fff]",text)):raise ReadingValidationError("Chinese content required")
    if re.search(r"https?://|```|<(?:system|assistant|think)>|the user wants|i want you to|ignore previous instructions|write a story|用户(?:想要|希望)|根据提供的信息|官方已证实|已经核实|已被证实",text,re.I):
        raise ReadingValidationError("Unsafe or unsupported narrative")
    # Evidence binding complements task-drift checks: unknown numbers/entities cannot pass solely as fluent prose.
    numbers=lambda value:set(re.findall(r"(?<![a-zA-Z])\d+(?:[.,]\d+)*",value))
    if numbers(text)-numbers(context):raise ReadingValidationError("Unprovided number in narrative")
    anchors=[]
    for entity in entities:
        anchors.extend(ALIASES.get(compact(entity),(entity,)))
    if anchors and not any(compact(value) in compact(text) for value in anchors):
        raise ReadingValidationError("Narrative lacks event entity evidence")


def validate_brief(result,data):
    indices=result.fact_indices
    if not set(indices)<=set(range(len(data.facts))) or len(indices)!=len(set(indices)):
        raise ReadingValidationError("Invalid fact evidence indices")
    chosen=[data.facts[i] for i in indices]
    context=" ".join(f["text"] for f in chosen)
    _grounded(result.title+"\n"+result.summary,context,data.entities)
    if any(f.get("status")=="conflicting" for f in data.facts) and not any(term in result.summary for term in ("冲突","矛盾","不同说法","尚无定论")):
        raise ReadingValidationError("Conflict uncertainty omitted")
    return result


def validate_composition(result,data):
    given={row["brief_id"]:row for row in data.briefs}
    ids=[row.brief_id for row in result.events]
    if set(ids)!=set(given) or len(ids)!=len(set(ids)):raise ReadingValidationError("Brief references differ from input")
    for paragraph in result.events:
        row=given[paragraph.brief_id]
        _grounded(paragraph.text,row["title"]+" "+row["summary"],row["entities"])
        if row["verification_status"]=="conflicting" and not any(term in paragraph.text for term in ("冲突","矛盾","不同说法","尚无定论")):
            raise ReadingValidationError("Conflicting Brief presented as fact")
    context=" ".join(row["title"]+" "+row["summary"] for row in data.briefs)
    entities=[entity for row in data.briefs for entity in row["entities"]]
    _grounded(result.title+" "+" ".join(result.core_updates+result.watch_points),context,entities)
    return result
