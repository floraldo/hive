import pytest
from app import app


@pytest.fixture
def client():
    """Create test client for Flask app"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint_exists(client):
    """Test that health endpoint exists and returns 200"""
    response = client.get('/api/health')
    assert response.status_code == 200


def test_health_endpoint_returns_json(client):
    """Test that health endpoint returns JSON"""
    response = client.get('/api/health')
    assert response.content_type == 'application/json'


def test_health_endpoint_returns_status_ok(client):
    """Test that health endpoint returns status ok"""
    response = client.get('/api/health')
    data = response.get_json()
    assert data['status'] == 'ok'


def test_health_endpoint_returns_timestamp(client):
    """Test that health endpoint includes timestamp"""
    response = client.get('/api/health')
    data = response.get_json()
    assert 'timestamp' in data
    assert data['timestamp'] is not None