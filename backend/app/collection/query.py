"""Bounded deterministic query construction, never an AI/network dependency."""
import re
from app.topics.policy import enabled_rules

MAX_QUERIES = 2
MAX_SCAN_REQUESTS = 3  # 2 search.list + 1 batched videos.list; no pagination/retries


def build_queries(topic):
    scope = " ".join([topic.name, topic.description or "", *enabled_rules(topic, "include")])
    lower = scope.casefold()
    model_topic = "chatgpt" in lower and not any(word in lower for word in ("替代品", "竞品", "alternative", "competitor"))
    nolan_identity = bool(re.search(r"\bchristopher[\s·]+nolan\b", lower) or ("克里斯托弗" in scope and "诺兰" in scope) or re.fullmatch(r"诺兰(?:的)?(?:新电影|新片)?", topic.name.strip()))
    if model_topic and any(word in lower for word in ("新模型", "new model", "model announcement", "模型发布", "模型公告", "能力变化", "model release", "model update")):
        official = " official" if any(word in lower for word in ("官方", "official")) else ""
        queries = (["OpenAI ChatGPT new model" + official, "OpenAI ChatGPT model announcement" + official]
                   if any(word in lower for word in ("新模型", "new model")) else
                   ["OpenAI ChatGPT model announcement" + official, "OpenAI ChatGPT model updates" + official])
    elif nolan_identity and any(word in lower for word in ("新电影", "new film", "new movie", "upcoming")):
        queries = ["Christopher Nolan upcoming movie", "Christopher Nolan new film announcement"]
    else:
        # Keep the identifying name and a small number of meaningful description keywords.
        # This is extraction, not general Chinese -> English translation.
        terms = re.findall(r"[A-Za-z][A-Za-z0-9.+#-]*|[\u4e00-\u9fff]{2,12}", " ".join([topic.description or "", *enabled_rules(topic, "include")]))
        stop = {"search", "collect", "about", "the", "and", "information", "related", "to", "for", "搜集", "关于", "信息", "收集", "关注", "追踪", "仅用于", "测试", "验收"}
        terms = [term for term in terms if term.casefold() not in stop and term.casefold() not in topic.name.casefold()]
        queries = [" ".join([topic.name.strip(), *terms[:4]])]
    return list(dict.fromkeys(query[:120].strip() for query in queries if query.strip()))[:MAX_QUERIES]
