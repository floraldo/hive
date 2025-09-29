from hive_logging import get_logger

logger = get_logger(__name__)

"""Configuration management for Hive Cache."""

import os
from typing import Any, Dict

from pydantic import BaseModel, Field, validator


class CacheConfig(BaseModel):
    """Configuration for Hive Cache client."""

    # Redis connection settings
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    max_connections: int = Field(default=20, description="Maximum Redis connections in pool")
    socket_keepalive: bool = Field(default=True, description="Enable TCP keepalive")
    socket_keepalive_options: Dict[str, int] = Field(
        default_factory=lambda: {"TCP_KEEPIDLE": 1, "TCP_KEEPINTVL": 3, "TCP_KEEPCNT": 5}
    )

    # Timeout settings
    socket_connect_timeout: float = Field(default=5.0, description="Socket connection timeout in seconds")
    socket_timeout: float = Field(default=5.0, description="Socket operation timeout in seconds")
    response_timeout: float = Field(default=5.0, description="Response timeout in seconds")

    # Circuit breaker settings
    circuit_breaker_enabled: bool = Field(default=True, description="Enable circuit breaker")
    circuit_breaker_threshold: int = Field(default=5, description="Failure threshold for circuit breaker")
    circuit_breaker_timeout: float = Field(default=60.0, description="Circuit breaker timeout in seconds")
    circuit_breaker_recovery_timeout: float = Field(default=30.0, description="Recovery timeout in seconds")

    # TTL settings
    default_ttl: int = Field(default=3600, description="Default TTL in seconds")
    max_ttl: int = Field(default=86400 * 7, description="Maximum TTL in seconds (7 days)")
    min_ttl: int = Field(default=60, description="Minimum TTL in seconds")

    # Performance settings
    compression_enabled: bool = Field(default=True, description="Enable compression for large values")
    compression_threshold: int = Field(default=1024, description="Compression threshold in bytes")
    compression_level: int = Field(default=6, description="Compression level (1-9)")

    # Serialization settings
    serialization_format: str = Field(default="orjson", description="Default serialization format")
    enable_json_fallback: bool = Field(default=True, description="Enable JSON fallback for serialization")

    # Monitoring settings
    health_check_enabled: bool = Field(default=True, description="Enable health checks")
    health_check_interval: float = Field(default=30.0, description="Health check interval in seconds")
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    enable_performance_monitoring: bool = Field(default=True, description="Enable detailed performance monitoring")
    performance_monitor_interval: float = Field(default=5.0, description="Performance monitoring collection interval")

    # Key management
    key_prefix: str = Field(default="hive:", description="Global key prefix")
    key_separator: str = Field(default=":", description="Key component separator")
    max_key_length: int = Field(default=250, description="Maximum key length")

    # Claude-specific settings
    claude_cache_namespace: str = Field(default="claude", description="Namespace for Claude API caches")
    claude_default_ttl: int = Field(default=3600, description="Default TTL for Claude responses")
    claude_max_response_size: int = Field(default=1024 * 1024, description="Max Claude response size to cache")

    # Performance cache settings
    performance_cache_namespace: str = Field(default="perf", description="Namespace for performance caches")
    performance_default_ttl: int = Field(default=86400, description="Default TTL for performance caches")

    @validator("redis_url")
    def validate_redis_url(cls, v):
        """Validate Redis URL format."""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("Redis URL must start with redis:// or rediss://")
        return v

    @validator("max_connections")
    def validate_max_connections(cls, v):
        """Validate connection pool size."""
        if v < 1:
            raise ValueError("max_connections must be at least 1")
        if v > 100:
            raise ValueError("max_connections should not exceed 100")
        return v

    @validator("default_ttl", "max_ttl", "min_ttl")
    def validate_ttl_values(cls, v):
        """Validate TTL values."""
        if v < 0:
            raise ValueError("TTL values must be non-negative")
        return v

    @validator("compression_level")
    def validate_compression_level(cls, v):
        """Validate compression level."""
        if not 1 <= v <= 9:
            raise ValueError("Compression level must be between 1 and 9")
        return v

    @validator("serialization_format")
    def validate_serialization_format(cls, v):
        """Validate serialization format."""
        valid_formats = ["msgpack", "orjson", "json"]  # Removed pickle for security
        if v not in valid_formats:
            raise ValueError(f"Serialization format must be one of: {valid_formats}")
        return v

    @classmethod
    def from_env(cls) -> "CacheConfig":
        """Create configuration from environment variables."""
        env_config = {}

        # Map environment variables to config fields
        env_mapping = {
            "HIVE_CACHE_REDIS_URL": "redis_url",
            "HIVE_CACHE_MAX_CONNECTIONS": "max_connections",
            "HIVE_CACHE_DEFAULT_TTL": "default_ttl",
            "HIVE_CACHE_CIRCUIT_BREAKER_THRESHOLD": "circuit_breaker_threshold",
            "HIVE_CACHE_COMPRESSION_THRESHOLD": "compression_threshold",
            "HIVE_CACHE_KEY_PREFIX": "key_prefix",
            "HIVE_CACHE_HEALTH_CHECK_INTERVAL": "health_check_interval",
        }

        for env_var, config_field in env_mapping.items():
            if env_value := os.getenv(env_var):
                # Convert to appropriate type
                if config_field in [
                    "max_connections",
                    "default_ttl",
                    "circuit_breaker_threshold",
                    "compression_threshold",
                ]:
                    env_config[config_field] = int(env_value)
                elif config_field in ["health_check_interval"]:
                    env_config[config_field] = float(env_value)
                else:
                    env_config[config_field] = env_value

        return cls(**env_config)

    def get_redis_connection_kwargs(self) -> Dict[str, Any]:
        """Get Redis connection parameters."""
        return {
            "socket_connect_timeout": self.socket_connect_timeout,
            "socket_timeout": self.socket_timeout,
            "socket_keepalive": self.socket_keepalive,
            "socket_keepalive_options": self.socket_keepalive_options,
            "max_connections": self.max_connections,
        }

    def get_namespaced_key(self, namespace: str, key: str) -> str:
        """Generate a namespaced cache key.

        Args:
            namespace: Cache namespace
            key: Original key

        Returns:
            Namespaced key with prefix
        """
        parts = [self.key_prefix.rstrip(self.key_separator), namespace, key]
        full_key = self.key_separator.join(parts)

        if len(full_key) > self.max_key_length:
            # Generate hash for long keys
            import hashlib

            key_hash = hashlib.sha256(full_key.encode()).hexdigest()[:16]
            full_key = f"{self.key_prefix}{namespace}{self.key_separator}hash{self.key_separator}{key_hash}"

        return full_key

    def get_ttl_for_namespace(self, namespace: str) -> int:
        """Get appropriate TTL for a namespace.

        Args:
            namespace: Cache namespace

        Returns:
            TTL in seconds
        """
        namespace_ttls = {
            self.claude_cache_namespace: self.claude_default_ttl,
            self.performance_cache_namespace: self.performance_default_ttl,
        }

        return namespace_ttls.get(namespace, self.default_ttl)
