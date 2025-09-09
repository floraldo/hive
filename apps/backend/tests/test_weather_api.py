"""
Tests for Weather API endpoints - Following TDD Protocol
RED: Create failing tests first
"""

import pytest
import json
import os
from unittest.mock import Mock, patch
from flask import Flask

# Import the app after setting up the environment
@pytest.fixture
def app():
    """Create and configure a test Flask app"""
    os.environ['OPENWEATHER_API_KEY'] = 'test_api_key'
    os.environ['FLASK_ENV'] = 'testing'
    
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app

@pytest.fixture
def client(app):
    """A test client for the app"""
    return app.test_client()

class TestWeatherAPI:
    
    @patch('weather_api.WeatherClient.get_weather')
    def test_weather_endpoint_success(self, mock_get_weather, client):
        """Test successful weather data retrieval from API endpoint"""
        # Mock WeatherClient response
        mock_get_weather.return_value = {
            "city": "London",
            "temperature": 15.5,
            "feels_like": 14.2,
            "humidity": 72,
            "description": "overcast clouds",
            "main": "Clouds"
        }
        
        response = client.get('/api/weather?city=London')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['city'] == 'London'
        assert data['temperature'] == 15.5
        assert data['description'] == 'overcast clouds'
        assert data['humidity'] == 72
        
        # Verify WeatherClient was called
        mock_get_weather.assert_called_once_with('London')
    
    def test_weather_endpoint_missing_city(self, client):
        """Test weather endpoint with missing city parameter"""
        response = client.get('/api/weather')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'City parameter is required' in data['error']
    
    def test_weather_endpoint_empty_city(self, client):
        """Test weather endpoint with empty city parameter"""
        response = client.get('/api/weather?city=')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'City parameter cannot be empty' in data['error']
    
    @patch('weather_api.WeatherClient.get_weather')
    def test_weather_endpoint_city_not_found(self, mock_get_weather, client):
        """Test weather endpoint with invalid city"""
        mock_get_weather.side_effect = ValueError("City not found")
        
        response = client.get('/api/weather?city=InvalidCity123')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'City not found' in data['error']
    
    @patch('weather_api.WeatherClient.get_weather')
    def test_weather_endpoint_api_error(self, mock_get_weather, client):
        """Test weather endpoint with WeatherClient API error"""
        mock_get_weather.side_effect = Exception("Weather API error: 500")
        
        response = client.get('/api/weather?city=London')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'Weather service error' in data['error']
    
    @patch('weather_api.WeatherClient.__init__')
    def test_weather_endpoint_missing_api_key(self, mock_init, client):
        """Test weather endpoint when API key is missing"""
        mock_init.side_effect = ValueError("OPENWEATHER_API_KEY not found in token vault")
        
        response = client.get('/api/weather?city=London')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'Configuration error' in data['error']
    
    def test_weather_endpoint_cors_headers(self, client):
        """Test that CORS headers are present"""
        response = client.get('/api/weather?city=London')
        
        # Check for CORS headers (should be added by Flask-CORS)
        assert 'Access-Control-Allow-Origin' in response.headers
    
    @patch('weather_api.WeatherClient.get_weather')
    def test_weather_endpoint_case_insensitive_city(self, mock_get_weather, client):
        """Test weather endpoint handles city names with different cases"""
        mock_get_weather.return_value = {
            "city": "London",  # API returns normalized case
            "temperature": 15.5,
            "feels_like": 14.2,
            "humidity": 72,
            "description": "overcast clouds",
            "main": "Clouds"
        }
        
        response = client.get('/api/weather?city=lOnDoN')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['city'] == 'London'
        
        # Verify WeatherClient was called with the original case
        mock_get_weather.assert_called_once_with('lOnDoN')