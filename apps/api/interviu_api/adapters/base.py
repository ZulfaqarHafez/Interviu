from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import CandidateResponse


class CandidateAdapterError(RuntimeError):
    """Raised when a candidate adapter cannot complete the ask contract."""


class CandidateAdapter(ABC):
    @abstractmethod
    async def ask(self, context: str, question: str) -> CandidateResponse:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None
