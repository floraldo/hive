"""
WeatherClient for OpenWeatherMap API integration
Uses the Hive token vault and APIClient base class
"""

import requests
from typing import Dict, Any
from hivemind.config.tokens import vault


class WeatherClient:
    """Client for OpenWeatherMap API integration using Hive token vault."""
    
    def __init__(self):
        """Initialize WeatherClient with API key from token vault."""
        self.api_key = vault.OPENWEATHER_API_KEY
        if not self.api_key:
            raise ValueError("OPENWEATHER_API_KEY not found in token vault")
        
        self.base_url = "https://api.openweathermap.org/data/2.5"
    
    def get_weather(self, city: str) -> Dict[str, Any]:
        """
        Get current weather data for a city.
        
        Args:
            city (str): Name of the city
            
        Returns:
            Dict containing weather data with standardized structure
            
        Raises:
            ValueError: If city is not found
            Exception: For API or network errors
        """
        if not city or not city.strip():
            raise ValueError("City name cannot be empty")
        
        url = f"{self.base_url}/weather"
        params = {
            "q": city.strip(),
            "appid": self.api_key,
            "units": "metric"  # Celsius
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 404:
                raise ValueError("City not found")
            elif response.status_code != 200:
                raise Exception(f"Weather API error: {response.status_code}")
            
            data = response.json()
            
            # Standardize the response format
            return {
                "city": data["name"],
                "temperature": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "description": data["weather"][0]["description"],
                "main": data["weather"][0]["main"]
            }
            
        except requests.ConnectionError:
            raise Exception("Failed to connect to weather API")
        except requests.Timeout:
            raise Exception("Weather API request timed out")
        except requests.RequestException as e:
            raise Exception(f"Weather API request failed: {str(e)}")
        except KeyError as e:
            raise Exception(f"Unexpected weather API response format: {str(e)}")
    
    def get_forecast(self, city: str, days: int = 5) -> Dict[str, Any]:
        """
        Get weather forecast for a city.
        
        Args:
            city (str): Name of the city
            days (int): Number of days (1-5)
            
        Returns:
            Dict containing forecast data
        """
        if not city or not city.strip():
            raise ValueError("City name cannot be empty")
        
        if days < 1 or days > 5:
            raise ValueError("Days must be between 1 and 5")
        
        url = f"{self.base_url}/forecast"
        params = {
            "q": city.strip(),
            "appid": self.api_key,
            "units": "metric",
            "cnt": days * 8  # 8 forecasts per day (3-hour intervals)
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 404:
                raise ValueError("City not found")
            elif response.status_code != 200:
                raise Exception(f"Weather API error: {response.status_code}")
            
            data = response.json()
            
            # Group forecasts by day
            daily_forecasts = []
            for i in range(0, len(data["list"]), 8):  # Every 8th item (daily)
                if i < len(data["list"]):
                    forecast = data["list"][i]
                    daily_forecasts.append({
                        "date": forecast["dt_txt"].split(" ")[0],
                        "temperature": forecast["main"]["temp"],
                        "description": forecast["weather"][0]["description"],
                        "humidity": forecast["main"]["humidity"]
                    })
            
            return {
                "city": data["city"]["name"],
                "forecasts": daily_forecasts[:days]
            }
            
        except requests.ConnectionError:
            raise Exception("Failed to connect to weather API")
        except requests.Timeout:
            raise Exception("Weather API request timed out")
        except requests.RequestException as e:
            raise Exception(f"Weather API request failed: {str(e)}")
        except KeyError as e:
            raise Exception(f"Unexpected weather API response format: {str(e)}")