from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rental_copilot.agent import InquiryAgent
from rental_copilot.api import create_app
from rental_copilot.config import load_settings
from rental_copilot.providers import MockProvider
from rental_copilot.seed import seed
from rental_copilot.store import Store
from rental_copilot.tools import ToolRegistry


@pytest.fixture
def settings():
    return load_settings(db_path=":memory:", llm_provider="mock")


@pytest.fixture
def store():
    s = Store(":memory:")
    seed(s)
    return s


@pytest.fixture
def tools():
    return ToolRegistry()


@pytest.fixture
def agent(store, settings, tools):
    return InquiryAgent(store, MockProvider(), settings, tools)


@pytest.fixture
def client(store, settings, tools):
    app = create_app(settings=settings, store=store, provider=MockProvider(), tools=tools)
    return TestClient(app)


def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}
