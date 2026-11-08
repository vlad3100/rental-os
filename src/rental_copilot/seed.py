"""Load the synthetic fixture into a fresh database."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .store import Store

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic.json"


def load_synthetic() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def seed(store: Store, include_inquiries: bool = True) -> None:
    data = load_synthetic()
    if not include_inquiries:
        data = {**data, "inquiries": []}
    store.init_schema(reset=True)
    store.load_fixture(data)
