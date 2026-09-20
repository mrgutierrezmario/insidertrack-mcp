"""The HTTP transport: bearer tokens, rate limit and the health route."""

import pytest
from starlette.testclient import TestClient

from insidertrack_mcp import server
from insidertrack_mcp.config import settings


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setattr(settings, "mcp_tokens", "tester:secret-1")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    with TestClient(server.http_app()) as client:
        yield client


def test_health_needs_no_token(http):
    response = http.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_mcp_without_token_is_401(http):
    response = http.post("/", json={})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_mcp_with_wrong_token_is_401(http):
    response = http.post("/", json={}, headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_rate_limit_after_configured_calls(http):
    headers = {"Authorization": "Bearer secret-1", "Accept": "application/json, text/event-stream"}
    statuses = [http.post("/", json={}, headers=headers).status_code for _ in range(4)]
    assert statuses[:3] != [401, 401, 401]
    assert statuses[3] == 429
