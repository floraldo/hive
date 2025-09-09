"""
Test for Hello endpoint
"""

import pytest
import json
from datetime import datetime
from app import app

@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_hello_endpoint(client):
    """Test hello endpoint returns correct response"""
    response = client.get('/api/hello')
    
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert data['message'] == "Hello from Hive!"
    assert data['service'] == "backend"
    assert 'timestamp' in data
    
    # Verify timestamp is valid ISO format
    timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
    assert isinstance(timestamp, datetime)

def test_hello_endpoint_content_type(client):
    """Test hello endpoint returns JSON content type"""
    response = client.get('/api/hello')
    assert response.content_type == 'application/json'