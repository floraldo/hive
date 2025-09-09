"""
Tests for the greeting API endpoint
Testing time-based personalized greetings
"""

import pytest
import json
from datetime import datetime
from unittest.mock import patch
from app import app

@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_greeting_endpoint_exists(client):
    """Test that greeting endpoint exists and returns valid response"""
    response = client.get('/api/greeting')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'message' in data
    assert 'time_of_day' in data
    assert 'timestamp' in data

def test_greeting_with_name_parameter(client):
    """Test greeting endpoint with name parameter"""
    response = client.get('/api/greeting?name=Alice')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'Alice' in data['message']

@patch('app.datetime')
def test_morning_greeting(mock_datetime, client):
    """Test morning greeting (6 AM - 12 PM)"""
    mock_datetime.now.return_value = datetime(2023, 1, 1, 9, 0, 0)  # 9 AM
    mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 9, 0, 0)
    
    response = client.get('/api/greeting')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['time_of_day'] == 'morning'
    assert 'morning' in data['message'].lower()

@patch('app.datetime')
def test_afternoon_greeting(mock_datetime, client):
    """Test afternoon greeting (12 PM - 6 PM)"""
    mock_datetime.now.return_value = datetime(2023, 1, 1, 14, 0, 0)  # 2 PM
    mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 14, 0, 0)
    
    response = client.get('/api/greeting')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['time_of_day'] == 'afternoon'
    assert 'afternoon' in data['message'].lower()

@patch('app.datetime')
def test_evening_greeting(mock_datetime, client):
    """Test evening greeting (6 PM - 6 AM)"""
    mock_datetime.now.return_value = datetime(2023, 1, 1, 20, 0, 0)  # 8 PM
    mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 20, 0, 0)
    
    response = client.get('/api/greeting')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['time_of_day'] == 'evening'
    assert 'evening' in data['message'].lower()