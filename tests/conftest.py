"""Shared fixtures: recorded InsiderTrack responses and a mocked upstream."""

import json
from pathlib import Path

import pytest
import respx

from insidertrack_mcp.config import settings

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    """Load a recorded API response by file name (without ``.json``)."""
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.fixture
def upstream():
    """A respx mock bound to the configured InsiderTrack URL."""
    with respx.mock(base_url=settings.insidertrack_url, assert_all_called=False) as mock:
        yield mock
