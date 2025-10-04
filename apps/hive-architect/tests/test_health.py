"""Test health endpoints for hive-architect."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_liveness_probe(test_app: TestClient) -> None:
    """Test liveness probe endpoint."""
    response = test_app.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == "hive-architect"
    assert "timestamp" in data


def test_readiness_probe(test_app: TestClient) -> None:
    """Test readiness probe endpoint."""
    response = test_app.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "hive-architect"
    assert "timestamp" in data
