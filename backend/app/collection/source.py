from abc import ABC, abstractmethod

from app.items.schemas import NormalizedItem


class SourceAdapter(ABC):
    name: str

    def enrich(self, items: list[NormalizedItem]) -> list[NormalizedItem]:
        """Optional single batch of actual source metrics; default has no network."""
        return items

    @abstractmethod
    def search(self, query: str) -> list[NormalizedItem]:
        """Return normalized content without writing to the database."""
        raise NotImplementedError
