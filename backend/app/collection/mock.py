"""Deterministic local fixtures, never a production information source."""
from datetime import datetime, timezone
from hashlib import sha256

from app.collection.source import SourceAdapter
from app.items.schemas import NormalizedItem


class MockSource(SourceAdapter):
    name = "mock"

    def search(self, query: str) -> list[NormalizedItem]:
        query = " ".join(query.split())
        identity = sha256(query.casefold().encode("utf-8")).hexdigest()
        titles = [f"{query} announces new project", f"Interview with {query}",
                  f"{query}: IMAX production update"]
        return [NormalizedItem(
            source=self.name, external_id=f"{identity}-{index}", title=title,
            url=f"http://localhost:3000/topics#mock-{identity}-{index}",
            author="SignalRadar Mock Studio",
            published_at=datetime(2026, 9, index, 12, tzinfo=timezone.utc),
            snippet=f"Simulated content about {query}. For local development and testing only.",
        ) for index, title in enumerate(titles, start=1)]
