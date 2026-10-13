"""Conservative deterministic information units; no AI calls or semantic clustering."""
import re
import unicodedata
from datetime import timezone
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from app.digests.schemas import DigestItem, DigestSource


def normalized(text):
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text or "").casefold())


def canonical_url(url):
    parts = urlsplit(url)
    query = sorted((key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
                   if not key.casefold().startswith("utm_") and key.casefold() not in ("fbclid", "gclid"))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(query), parts.fragment))


def same_event(left, right):
    if canonical_url(left.url) == canonical_url(right.url):
        return True
    lt, rt = normalized(left.title), normalized(right.title)
    ls, rs = normalized(left.ai_summary), normalized(right.ai_summary)
    # Distinct version/date/episode numbers are strong evidence against merging.
    if re.findall(r"\d+", lt) != re.findall(r"\d+", rt):
        return False
    a, b = left.published_at, right.published_at
    if a is not None and b is not None:
        a = a.replace(tzinfo=timezone.utc) if a.tzinfo is None else a
        b = b.replace(tzinfo=timezone.utc) if b.tzinfo is None else b
        if abs((a-b).total_seconds()) > 2 * 86400:
            return False
    elif lt != rt or ls != rs:
        return False
    # Near-equal strings can change a decisive word (announced/denied).
    words = lambda title: set(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", title).casefold())) - {"the", "a", "an", "news", "breaking"}
    chinese_left = "".join(re.findall(r"[\u4e00-\u9fff]", left.title))
    chinese_right = "".join(re.findall(r"[\u4e00-\u9fff]", right.title))
    if words(left.title) != words(right.title) or chinese_left != chinese_right:
        return False
    # Generic short summaries and a one-word entity change are not reliable event matches.
    # Require identical normalized facts rather than letting long boilerplate hide a change.
    return bool(len(lt) >= 12 and len(ls) >= 20 and ls == rs
                and (lt == rt or SequenceMatcher(None, lt, rt).ratio() >= .94))


def consolidate(records, max_units=10):
    groups = []
    for record in records:
        # Complete-link rather than a similarity chain joining unrelated events.
        group = next((group for group in groups if all(same_event(old, record) for old in group)), None)
        if group is not None:
            group.append(record)
        elif len(groups) < max_units:
            groups.append([record])
    units = []
    for index, group in enumerate(groups, 1):
        lead = group[0]
        unit_id = f"U{index}"
        refs = [DigestSource(item_id=row.id, unit_id=unit_id, title=row.title, source=row.source,
                             url=row.url, author=row.author, published_at=row.published_at) for row in group]
        units.append(DigestItem(title=lead.title[:300], source=lead.source,
            author=lead.author[:100] if lead.author else None, published_at=lead.published_at,
            ai_category=lead.ai_category, ai_relevance_score=lead.ai_relevance_score,
            ai_summary="\n".join(dict.fromkeys(row.ai_summary for row in sorted(group, key=lambda row: row.id)))[:1500], unit_id=unit_id, item_ids=[row.id for row in group], source_refs=refs))
    return units
