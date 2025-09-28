"""
Health endpoint tests for {{project_name}}
"""

import pytest
import json
from app import app


@pytest.fixture
def client():
    """Test client fixture"""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    """Test the health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["status"] == "healthy"
    assert data["service"] == "{{project_name}}"
    assert "version" in data
    assert "environment" in data


def test_app_info(client):
    """Test the app info endpoint"""
    response = client.get("/api/info")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["name"] == "{{project_name}}"
    assert data["description"] == "{{project_description}}"
    assert data["version"] == "1.0.0"
    assert data["framework"] == "Flask"
    assert data["features"]["cors"] is True
    assert data["features"]["logging"] is True


def test_404_error(client):
    """Test 404 error handling"""
    response = client.get("/api/nonexistent")
    assert response.status_code == 404

    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Not found"
