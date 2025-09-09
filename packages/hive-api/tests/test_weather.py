"""
Tests for WeatherClient - Following TDD Protocol
RED: Create failing tests first
"""

import pytest
import requests
import os
from unittest.mock import Mock, patch
from hive_api.weather import WeatherClient


class TestWeatherClient:
    
    @patch.dict(os.environ, {'OPENWEATHER_API_KEY': '5b3c76f642bf7905a7b5d2f94f4b3c27'})
    def test_weather_client_initialization(self):
        """Test WeatherClient can be initialized with API key from vault"""
        client = WeatherClient()
        assert client.api_key is not None
        assert len(client.api_key) > 0
    
    @patch.dict(os.environ, {}, clear=True)
    def test_weather_client_missing_api_key(self):
        """Test WeatherClient raises error when API key is missing"""
        with pytest.raises(ValueError, match="OPENWEATHER_API_KEY not found in token vault"):
            WeatherClient()
    
    @patch.dict(os.environ, {'OPENWEATHER_API_KEY': '5b3c76f642bf7905a7b5d2f94f4b3c27'})
    @patch('hive_api.weather.requests.get')
    def test_get_weather_success(self, mock_get):
        """Test successful weather data retrieval"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "London",
            "main": {
                "temp": 15.5,
                "feels_like": 14.2,
                "humidity": 72
            },
            "weather": [
                {
                    "main": "Clouds",
                    "description": "overcast clouds"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        client = WeatherClient()
        weather_data = client.get_weather("London")
        
        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "London" in str(call_args)
        
        # Verify returned data structure
        assert weather_data["city"] == "London"
        assert weather_data["temperature"] == 15.5
        assert weather_data["description"] == "overcast clouds"
        assert weather_data["humidity"] == 72
    
    @patch.dict(os.environ, {'OPENWEATHER_API_KEY': '5b3c76f642bf7905a7b5d2f94f4b3c27'})
    @patch('hive_api.weather.requests.get')
    def test_get_weather_city_not_found(self, mock_get):
        """Test handling of invalid city name"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "city not found"}
        mock_get.return_value = mock_response
        
        client = WeatherClient()
        
        with pytest.raises(ValueError, match="City not found"):
            client.get_weather("InvalidCity123")
    
    @patch.dict(os.environ, {'OPENWEATHER_API_KEY': '5b3c76f642bf7905a7b5d2f94f4b3c27'})
    @patch('hive_api.weather.requests.get')
    def test_get_weather_api_error(self, mock_get):
        """Test handling of API errors"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "Internal server error"}
        mock_get.return_value = mock_response
        
        client = WeatherClient()
        
        with pytest.raises(Exception, match="Weather API error"):
            client.get_weather("London")
    
    @patch.dict(os.environ, {'OPENWEATHER_API_KEY': '5b3c76f642bf7905a7b5d2f94f4b3c27'})
    @patch('hive_api.weather.requests.get')
    def test_get_weather_network_error(self, mock_get):
        """Test handling of network errors"""
        mock_get.side_effect = requests.ConnectionError("Network error")
        
        client = WeatherClient()
        
        with pytest.raises(Exception, match="Failed to connect to weather API"):
            client.get_weather("London")