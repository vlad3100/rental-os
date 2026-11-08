"""Settings from environment variables (and an optional .env file).

Why a tiny loader instead of a library: the whole configuration surface is six
variables, and keeping it explicit makes the safety rule visible — v0.1 refuses
to start in anything but synthetic mode.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_PROVIDERS = {"mock", "anthropic"}


class ConfigError(RuntimeError):
    pass


def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines. Existing environment variables always win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    data_mode: str
    llm_provider: str
    anthropic_model: str
    anthropic_effort: str
    db_path: Path
    confidence_threshold: float


def load_settings(**overrides: object) -> Settings:
    _load_dotenv(REPO_ROOT / ".env")
    data_mode = str(overrides.get("data_mode") or os.getenv("RC_DATA_MODE", "synthetic"))
    if data_mode != "synthetic":
        raise ConfigError(
            "Only RC_DATA_MODE=synthetic is supported in v0.1. Real pilot data needs a DPA, "
            "security review and legal review first (see docs/02-build/threat-model.md)."
        )
    provider = str(overrides.get("llm_provider") or os.getenv("RC_LLM_PROVIDER", "mock")).lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ConfigError(f"RC_LLM_PROVIDER must be one of {sorted(SUPPORTED_PROVIDERS)}, got {provider!r}")
    db_value = overrides.get("db_path") or os.getenv("RC_DB_PATH", "var/rental_copilot.db")
    db_path = Path(str(db_value))
    if str(db_value) != ":memory:" and not db_path.is_absolute():
        db_path = REPO_ROOT / db_path
    threshold = float(overrides.get("confidence_threshold") or os.getenv("RC_CONFIDENCE_THRESHOLD", "0.6"))
    if not 0.0 < threshold < 1.0:
        raise ConfigError("RC_CONFIDENCE_THRESHOLD must be between 0 and 1")
    effort = str(overrides.get("anthropic_effort") or os.getenv("RC_ANTHROPIC_EFFORT", "medium")).lower()
    if effort not in {"low", "medium", "high", "xhigh", "max"}:
        raise ConfigError("RC_ANTHROPIC_EFFORT must be low, medium, high, xhigh or max")
    return Settings(
        data_mode=data_mode,
        llm_provider=provider,
        anthropic_model=str(overrides.get("anthropic_model") or os.getenv("RC_ANTHROPIC_MODEL", "claude-opus-5-5")),
        anthropic_effort=effort,
        db_path=db_path,
        confidence_threshold=threshold,
    )
