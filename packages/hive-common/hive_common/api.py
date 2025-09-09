"""
API client utilities for Hive applications
"""

import requests
from typing import Dict, Any, Optional
import json

class APIClient:
    """Generic API client with common functionality."""
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
    
    def set_auth_header(self, token: str, header_name: str = 'Authorization'):
        """Set authentication header for all requests."""
        self.session.headers[header_name] = f'Bearer {token}'
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make POST request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.post(
            url, 
            json=data, 
            timeout=self.timeout,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        return response.json()
    
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make PUT request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.put(
            url, 
            json=data, 
            timeout=self.timeout,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        return response.json()
    
    def delete(self, endpoint: str) -> bool:
        """Make DELETE request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.delete(url, timeout=self.timeout)
        response.raise_for_status()
        return response.status_code == 204