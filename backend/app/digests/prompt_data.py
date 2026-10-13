"""Bounded quoted model data; full source URLs/titles remain in persisted snapshots."""
import json

DIGEST_DATA_MAX_BYTES = 10_000


def render_digest_data(data):
    def quoted(value):
        return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    items = []
    for item in data.items:
        value = item.model_dump(mode="json", exclude={"source_refs"})
        # No duplicated long URLs/titles in the model context. Links are program-owned.
        value["source_refs"] = [{"item_id": ref.item_id, "unit_id": ref.unit_id, "source": ref.source[:100],
            "author": ref.author[:100] if ref.author else None, "published_at": ref.published_at.isoformat() if ref.published_at else None}
            for ref in item.source_refs]
        items.append("<ITEM>\n" + quoted(value) + "\n</ITEM>")
    return "<TOPIC>\n" + quoted({"name": data.topic_name, "description": data.topic_description}) + "\n</TOPIC>\n<ITEMS>\n" + "\n".join(items) + "\n</ITEMS>"
