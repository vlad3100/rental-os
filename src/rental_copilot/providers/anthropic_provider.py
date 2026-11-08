"""Claude provider (optional).

Install with `uv sync --extra claude`; credentials come from ANTHROPIC_API_KEY or an
`ant auth login` profile. Design choices:
- Structured outputs via `messages.parse(output_format=...)`: the response must match a
  schema. We still re-validate into the domain models, because a schema-valid answer can
  still be wrong (confidence > 1, unknown field names, a fact id that does not exist).
- `fallbacks="default"`: if a safety classifier declines the request, the API re-runs it on
  Anthropic's recommended fallback model instead of returning a refusal.
- Effort is set explicitly (Opus 5.5 defaults to medium). Thinking stays on (it cannot be
  disabled on this model); max_tokens leaves room for it.
- Every failure becomes a ProviderError, which the agent turns into human review.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from ..catalog import FIELDS
from ..domain import Classification, DraftProposal, DraftRequest, Intent
from .base import CallStats, ProviderError

PROMPT_VERSION = "inquiry-v1"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "inquiry_v1.md"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class _ClassificationWire(BaseModel):
    intent: Intent
    secondary_intents: list[Intent]
    language: Literal["de", "en", "other"]
    asked_fields: list[str]
    confidence: float
    rationale: str


class _DraftWire(BaseModel):
    response_text: str
    fact_ids_used: list[str]
    unknown_fields: list[str]
    proposed_slot_ids: list[str]
    knowledge_ids_used: list[str]
    rationale: str


W = TypeVar("W", bound=BaseModel)


def wrap_untrusted(message: str) -> str:
    """Delimit the applicant's text and remove any attempt to close the delimiter early."""
    cleaned = re.sub(r"<\s*/?\s*applicant_message\s*>", "", message, flags=re.IGNORECASE)
    return f"<applicant_message>\n{cleaned}\n</applicant_message>"


class AnthropicProvider:
    prompt_version = PROMPT_VERSION

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "medium", timeout_s: float = 90.0,
                 max_retries: int = 2, client: Any = None):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on the optional extra
            raise ProviderError("sdk_missing", "install the claude extra: uv sync --extra claude") from exc
        self._sdk = anthropic
        self.client = client or anthropic.Anthropic(timeout=timeout_s, max_retries=max_retries)
        self.model = model
        self.effort = effort
        self.system = PROMPT_PATH.read_text(encoding="utf-8")
        self.name = f"anthropic:{model}"

    def _call(self, user_content: str, wire: type[W]) -> tuple[W, CallStats]:
        sdk = self._sdk
        start = time.perf_counter()
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=16000,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                system=self.system,
                output_config={"effort": self.effort},
                output_format=wire,
                messages=[{"role": "user", "content": user_content}],
            )
        except sdk.APITimeoutError as exc:
            raise ProviderError("timeout") from exc
        except sdk.RateLimitError as exc:
            raise ProviderError("rate_limited") from exc
        except sdk.BadRequestError as exc:
            raise ProviderError("bad_request", str(exc.message)[:200]) from exc
        except sdk.APIStatusError as exc:
            raise ProviderError(f"api_status_{exc.status_code}") from exc
        except sdk.APIConnectionError as exc:
            raise ProviderError("connection_error") from exc
        except ValueError as exc:  # includes pydantic.ValidationError from parsing
            raise ProviderError("schema_validation", str(exc)[:200]) from exc
        latency_ms = int((time.perf_counter() - start) * 1000)
        if response.stop_reason == "refusal":
            raise ProviderError("refusal")
        if response.stop_reason == "max_tokens":
            raise ProviderError("max_tokens")
        parsed = response.parsed_output
        if parsed is None:
            raise ProviderError("no_structured_output")
        usage = response.usage
        return parsed, CallStats(latency_ms=latency_ms, input_tokens=getattr(usage, "input_tokens", None),
                                 output_tokens=getattr(usage, "output_tokens", None))

    def classify(self, message: str, unit_fields: list[str]) -> tuple[Classification, CallStats]:
        allowed = "\n".join(f"- {f}: {FIELDS[f].label_de} / {FIELDS[f].label_en}" for f in unit_fields if f in FIELDS)
        content = f"Task: classify\n\nAllowed fact fields:\n{allowed}\n\n{wrap_untrusted(message)}"
        wire, stats = self._call(content, _ClassificationWire)
        try:
            result = Classification(
                intent=wire.intent,
                secondary_intents=[i for i in wire.secondary_intents if i != wire.intent][:4],
                language=wire.language,
                asked_fields=[f for f in dict.fromkeys(wire.asked_fields) if f in unit_fields][:12],
                confidence=wire.confidence,
                rationale=wire.rationale[:400],
            )
        except ValidationError as exc:
            raise ProviderError("invalid_classification", str(exc)[:200]) from exc
        return result, stats

    def draft(self, request: DraftRequest) -> tuple[DraftProposal, CallStats]:
        context = request.model_dump(mode="json", exclude={"message"})
        content = ("Task: draft\n\nContext (JSON):\n" + json.dumps(context, ensure_ascii=False, indent=1)
                   + "\n\n" + wrap_untrusted(request.message))
        wire, stats = self._call(content, _DraftWire)
        try:
            proposal = DraftProposal(**wire.model_dump())
        except ValidationError as exc:
            raise ProviderError("invalid_draft", str(exc)[:200]) from exc
        return proposal, stats
