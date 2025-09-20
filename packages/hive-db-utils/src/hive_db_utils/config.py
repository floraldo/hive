"""
Configuration utilities for Hive applications
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration management for Hive applications."""
    
    def __init__(self):
        self.env = os.environ.get('ENVIRONMENT', 'development')
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get configuration value from environment."""
        return os.environ.get(key, default)
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        try:
            return int(os.environ.get(key, default))
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = os.environ.get(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.env == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.env == 'development'
    
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.env == 'testing'

# Global configuration instance
config = Config()

def get_config() -> Config:
    """Get the global configuration instance."""
    return config