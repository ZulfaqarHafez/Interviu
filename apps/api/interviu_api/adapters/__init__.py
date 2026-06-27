from .base import CandidateAdapter, CandidateAdapterError
from .factory import adapter_for
from .http import HttpCandidateAdapter
from .mock import MockCandidateAdapter

__all__ = [
    "CandidateAdapter",
    "CandidateAdapterError",
    "HttpCandidateAdapter",
    "MockCandidateAdapter",
    "adapter_for",
]
