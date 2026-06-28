from .base import CandidateAdapter, CandidateAdapterError
from .factory import adapter_for
from .http import HttpCandidateAdapter
from .mock import MockCandidateAdapter
from .prompt import PromptAgentAdapter

__all__ = [
    "CandidateAdapter",
    "CandidateAdapterError",
    "HttpCandidateAdapter",
    "MockCandidateAdapter",
    "PromptAgentAdapter",
    "adapter_for",
]
