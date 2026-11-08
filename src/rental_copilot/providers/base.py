"""Provider interface. Every model call goes through one of two narrow methods.

A provider only *proposes*: a classification and a draft. It never changes state,
never calls tools and never sends anything. The agent validates every output and the
guardrails check every draft, whatever the provider is.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..domain import Classification, DraftProposal, DraftRequest


class ProviderError(RuntimeError):
    """The model call failed or returned unusable output. Always leads to human review."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass
class CallStats:
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    name: str
    prompt_version: str

    def classify(self, message: str, unit_fields: list[str]) -> tuple[Classification, CallStats]: ...

    def draft(self, request: DraftRequest) -> tuple[DraftProposal, CallStats]: ...
