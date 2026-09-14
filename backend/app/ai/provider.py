from abc import ABC, abstractmethod

from app.ai.schemas import AnalysisInput, AnalysisResult


class AIError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class AIProvider(ABC):
    @abstractmethod
    def analyze(self, data: AnalysisInput) -> AnalysisResult:
        """Return validated analysis without database access."""
        raise NotImplementedError
