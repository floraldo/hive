"""
Weather API Blueprint - Flask endpoint for weather data
Uses hive_api.WeatherClient with token vault integration
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
from hive_api import WeatherClient

weather_bp = Blueprint('weather', __name__)


@weather_bp.route('/api/weather', methods=['GET'])
def get_weather():
    """
    Get weather data for a city.
    
    Query Parameters:
        city (str): Name of the city
        
    Returns:
        JSON response with weather data or error message
    """
    try:
        # Validate city parameter
        city = request.args.get('city')
        if city is None:
            return jsonify({
                'success': False,
                'error': 'City parameter is required'
            }), 400
        
        city = city.strip()
        if not city:
            return jsonify({
                'success': False,
                'error': 'City parameter cannot be empty'
            }), 400
        
        # Initialize WeatherClient
        try:
            weather_client = WeatherClient()
        except ValueError as e:
            if "OPENWEATHER_API_KEY not found" in str(e):
                return jsonify({
                    'success': False,
                    'error': 'Configuration error: Weather service not available'
                }), 500
            raise
        
        # Get weather data
        try:
            weather_data = weather_client.get_weather(city)
            
            # Return successful response
            return jsonify({
                'success': True,
                'city': weather_data['city'],
                'temperature': weather_data['temperature'],
                'feels_like': weather_data['feels_like'],
                'humidity': weather_data['humidity'],
                'description': weather_data['description'],
                'main': weather_data['main']
            }), 200
            
        except ValueError as e:
            if "City not found" in str(e):
                return jsonify({
                    'success': False,
                    'error': 'City not found'
                }), 404
            raise
            
        except Exception as e:
            error_msg = str(e)
            if "Weather API error" in error_msg or "Failed to connect" in error_msg:
                return jsonify({
                    'success': False,
                    'error': 'Weather service error: Unable to retrieve weather data'
                }), 500
            raise
            
    except Exception as e:
        # Generic error handler
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@weather_bp.route('/api/weather/forecast', methods=['GET'])
def get_forecast():
    """
    Get weather forecast for a city.
    
    Query Parameters:
        city (str): Name of the city
        days (int, optional): Number of forecast days (1-5, default 5)
        
    Returns:
        JSON response with forecast data or error message
    """
    try:
        # Validate city parameter
        city = request.args.get('city')
        if city is None:
            return jsonify({
                'success': False,
                'error': 'City parameter is required'
            }), 400
        
        city = city.strip()
        if not city:
            return jsonify({
                'success': False,
                'error': 'City parameter cannot be empty'
            }), 400
        
        # Parse days parameter
        days = request.args.get('days', '5')
        try:
            days = int(days)
            if days < 1 or days > 5:
                return jsonify({
                    'success': False,
                    'error': 'Days parameter must be between 1 and 5'
                }), 400
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Days parameter must be a valid number'
            }), 400
        
        # Initialize WeatherClient
        try:
            weather_client = WeatherClient()
        except ValueError as e:
            if "OPENWEATHER_API_KEY not found" in str(e):
                return jsonify({
                    'success': False,
                    'error': 'Configuration error: Weather service not available'
                }), 500
            raise
        
        # Get forecast data
        try:
            forecast_data = weather_client.get_forecast(city, days)
            
            # Return successful response
            return jsonify({
                'success': True,
                'city': forecast_data['city'],
                'forecasts': forecast_data['forecasts']
            }), 200
            
        except ValueError as e:
            if "City not found" in str(e):
                return jsonify({
                    'success': False,
                    'error': 'City not found'
                }), 404
            raise
            
        except Exception as e:
            error_msg = str(e)
            if "Weather API error" in error_msg or "Failed to connect" in error_msg:
                return jsonify({
                    'success': False,
                    'error': 'Weather service error: Unable to retrieve forecast data'
                }), 500
            raise
            
    except Exception as e:
        # Generic error handler
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500