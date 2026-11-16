"""Conservative, deterministic preprocessing. Never changes the stored Raw Item."""
import re
import unicodedata
from html import unescape
from html.parser import HTMLParser
from dataclasses import dataclass


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        elif not self.hidden and tag in ("p", "div", "br", "li", "h1", "h2", "section"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ("p", "div", "li", "h1", "h2", "section"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_text(value):
    parser = _Text()
    parser.feed(value or "")
    parser.close()
    text = unicodedata.normalize("NFKC", unescape("".join(parser.parts)))
    text = re.sub(r"[\u200b\ufeff\u2060]", "", text).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line for raw in text.splitlines() if (line := re.sub(r"[^\S\n]+", " ", raw).strip()))


@dataclass(frozen=True)
class PreprocessedText:
    title: str
    body: str
    matching_text: str
    metadata: dict


class TextPreprocessor:
    def process(self, title, body, source, author=None):
        title, body = clean_text(title), clean_text(body)
        metadata = {"source": source, "author": author, "attributions": [], "copyright": []}
        lines = body.splitlines()
        if lines and lines[0] == title:
            lines.pop(0)  # exact repeated heading only
        retained = []
        for line in lines:
            if re.fullmatch(r"(?:作者|来源|Source|Author)\s*[:：]\s*[^。!?！？]{1,100}", line, re.I):
                metadata["attributions"].append(line)
            elif re.fullmatch(r"(?:©|Copyright\s*(?:©|\(c\))?|版权所有)\s*(?:19|20)\d{2}[^。!?！？]{0,100}", line, re.I):
                metadata["copyright"].append(line)
            elif re.fullmatch(r"[-_=*·•]{3,}", line):
                continue  # formatting-only separator, not factual text
            else:
                retained.append(line)
        body = "\n".join(retained)
        matching = re.sub(r"[\W_]+", " ", (title + " " + body).casefold()).strip()
        return PreprocessedText(title, body, matching, metadata)
