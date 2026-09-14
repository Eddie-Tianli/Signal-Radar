from abc import ABC, abstractmethod

from app.items.schemas import NormalizedItem


class SourceAdapter(ABC):
    @abstractmethod
    def search(self, query: str) -> list[NormalizedItem]:
        """Return normalized content without writing to the database."""
        raise NotImplementedError
