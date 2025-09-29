from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Configuration data models for climate module.

Extracted to avoid circular dependencies between settings.py and base.py.
"""

from dataclasses import dataclass
from enum import Enum


class RateLimitStrategy(Enum):
    """Rate limiting strategies"""

    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"


@dataclass
class HTTPConfig:
    """HTTP client configuration"""

    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 1
    user_agent: str = "EcoSystemiser/1.0"
    connection_pool_size: int = 100
    max_connections_per_host: int = 30
    keepalive_expiry: int = 30
    verify_ssl: bool = True
    follow_redirects: bool = True
    retry_backoff_factor: float = 2.0


@dataclass
class CacheConfig:
    """Cache configuration for adapters"""

    memory_size: int = 128  # MB
    memory_ttl: int = 3600  # seconds
    cache_dir: str = "/tmp/ecosystemiser_cache"
    disk_ttl: int = 86400  # seconds
    redis_url: str | None = None
    redis_ttl: int = 7200  # seconds


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""

    requests_per_minute: int = 60
    requests_per_hour: int | None = None
    requests_per_day: int | None = None
    burst_size: int = 10
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
