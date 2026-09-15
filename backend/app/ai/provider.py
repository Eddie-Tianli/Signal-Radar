from abc import ABC, abstractmethod

from app.ai.schemas import AnalysisInput, AnalysisResult
from app.digests.schemas import DigestInput, DigestResult


class AIError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class AIProvider(ABC):
    def digest(self, data: DigestInput) -> DigestResult:
        """Generate a structured brief; providers opt in to this capability."""
        raise AIError("This AI provider does not support Digests.", 503)

    @abstractmethod
    def analyze(self, data: AnalysisInput) -> AnalysisResult:
        """Return validated analysis without database access."""
        raise NotImplementedError
