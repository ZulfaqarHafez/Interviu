from __future__ import annotations

from ..models import CandidateConfig
from .base import CandidateAdapter, CandidateAdapterError
from .http import HttpCandidateAdapter
from .mock import MockCandidateAdapter


def adapter_for(config: CandidateConfig) -> CandidateAdapter:
    if config.adapter_type == "mock":
        return MockCandidateAdapter(config)
    if config.adapter_type == "http":
        return HttpCandidateAdapter(config)
    raise CandidateAdapterError(
        f"Adapter '{config.adapter_type}' is registered but not implemented in the MVP."
    )
