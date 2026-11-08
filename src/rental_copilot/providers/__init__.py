from __future__ import annotations

from ..config import Settings
from .base import CallStats, LLMProvider, ProviderError
from .mock import MockProvider

__all__ = ["CallStats", "LLMProvider", "MockProvider", "ProviderError", "make_provider"]


def make_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockProvider()
    from .anthropic_provider import AnthropicProvider

    return AnthropicProvider(model=settings.anthropic_model, effort=settings.anthropic_effort)
