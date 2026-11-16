"""Small inspectable aliases and fingerprints; never broad keyword clustering."""
import hashlib
import json
import re
import unicodedata
from app.digests.consolidation import canonical_url

ALIASES = {"openai":("OpenAI","开放人工智能"),"chatgpt":("ChatGPT",),
    "christophernolan":("Christopher Nolan","克里斯托弗·诺兰","克里斯托弗诺兰","诺兰"),
    "nvidia":("NVIDIA","英伟达"),"amd":("AMD","超威半导体")}


def compact(value):
    return re.sub(r"[\W_]+","",unicodedata.normalize("NFKC",value or "").casefold())


def entity_key(value):
    normalized=compact(value)
    for key,aliases in ALIASES.items():
        if normalized in {compact(alias) for alias in aliases}:return key
    return normalized[:240]


def entity_keys(values):
    return sorted({entity_key(value) for value in (values or []) if entity_key(value)})


def fact_key(text):
    value=unicodedata.normalize("NFKC",text or "").casefold()
    for key,aliases in ALIASES.items():
        for alias in sorted(aliases,key=len,reverse=True):
            value=re.sub(re.escape(alias),key,value,flags=re.I)
    return compact(value)


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()


def url_key(value):return digest(canonical_url(value))


def family(event_type):
    value=compact(event_type)
    if value in {"productrelease","modelrelease","modelupdate","priceannouncement","pricing","priceupdate","产品发布","模型发布","模型更新","售价公布","产品定价"}:return "product"
    if value in {"acquisition","merger","收购","并购"}:return "acquisition"
    if value in {"filmproduction","casting","filmrelease","电影制作","选角","电影上映"}:return "film"
    if value in {"news","新闻","公司声明","公告","公司公告","statement","announcement"}:return "unknown"
    return value or "unknown"


def product_keys(text):
    # An explicit version/product anchor, not a generic company name or a bare price.
    return {compact(value) for value in re.findall(r"\b[a-z][a-z-]{1,20}[- ]?\d[\w.-]{0,20}\b",unicodedata.normalize("NFKC",text).casefold())}


def structured(record):
    return {"normalization_id":record.id,"schema_version":record.schema_version,"revision":record.revision,"model_name":record.model_name,"headline":record.headline,"summary":record.summary,
        "entities":record.entities or [],"event_type":record.event_type,"event_date":str(record.event_date) if record.event_date else None,
        "keywords":record.keywords or [],"claims":record.claims or [],"warnings":record.warnings or []}


def direct_subject_action(claim, aliases):
    value=unicodedata.normalize("NFKC",claim).casefold()
    for alias in aliases:
        actor=re.escape(unicodedata.normalize("NFKC",alias).casefold())
        pattern=rf"(?<![a-z0-9]){actor}(?![a-z0-9])(?:公司)?(?:称其|称|表示|已|将|正式|计划|联合|今日|今天|刚刚|宣布|\s+(?:has|will|reportedly)){{0,3}}\s*(?:发布|宣布|公布|推出|收购|上映|拍摄|announce[sd]?|release[sd]?|launch(?:ed|es)?|acquire[sd]?)"
        if re.search(pattern,value):return True
    return False


def evidence_key(claim):return fact_key(claim["text"])+(":conflict" if claim.get("status")=="conflicting" else "")


def concrete_price(text):
    return bool(re.search(r"(?:售价|定价|价格|price(?:d)?)(?:\s*(?:为|是|约|定为|at|is|of|:|：))*\s*(?:usd\s*|[$¥￥€£])?\d+(?:[.,]\d+)*",text,re.I))
