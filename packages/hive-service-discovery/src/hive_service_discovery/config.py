from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""Configuration for service discovery components."""

import os

from pydantic import BaseModel, Field, validator


class HealthCheckConfig(BaseModel):
    """Configuration for health checks."""

    enabled: bool = Field(default=True, description="Enable health checks")
    interval: float = Field(default=30.0, description="Health check interval in seconds")
    timeout: float = Field(default=5.0, description="Health check timeout in seconds")
    failure_threshold: int = Field(default=3, description="Consecutive failures before marking unhealthy")
    success_threshold: int = Field(default=2, description="Consecutive successes to mark healthy")
    http_path: str = Field(default="/health", description="HTTP health check path")

    @validator("interval", "timeout")
    def validate_positive_time(cls, v):
        if v <= 0:
            raise ValueError("Time values must be positive")
        return v


class LoadBalancerConfig(BaseModel):
    """Configuration for load balancing."""

    strategy: str = Field(default="round_robin", description="Load balancing strategy")
    enable_sticky_sessions: bool = Field(default=False, description="Enable sticky sessions")
    max_retries: int = Field(default=3, description="Maximum retries for failed requests")
    circuit_breaker_threshold: int = Field(default=5, description="Circuit breaker failure threshold")
    circuit_breaker_timeout: float = Field(default=60.0, description="Circuit breaker timeout in seconds")

    @validator("strategy")
    def validate_strategy(cls, v):
        valid_strategies = ["round_robin", "least_connections", "random", "weighted", "health_based"]
        if v not in valid_strategies:
            raise ValueError(f"Strategy must be one of: {valid_strategies}")
        return v


class ServiceDiscoveryConfig(BaseModel):
    """Main configuration for service discovery."""

    # Service registry settings
    registry_backend: str = Field(default="redis", description="Registry backend (redis, consul, etcd)")
    registry_url: str = Field(default="redis://localhost:6379/1", description="Registry backend URL")

    # Service registration settings
    service_ttl: int = Field(default=60, description="Service registration TTL in seconds")
    registration_retry_attempts: int = Field(default=3, description="Registration retry attempts")
    registration_retry_delay: float = Field(default=5.0, description="Registration retry delay in seconds")

    # Discovery settings
    discovery_interval: float = Field(default=10.0, description="Service discovery refresh interval")
    cache_ttl: int = Field(default=30, description="Service cache TTL in seconds")

    # Health monitoring
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)

    # Load balancing
    load_balancer: LoadBalancerConfig = Field(default_factory=LoadBalancerConfig)

    # Network settings
    bind_address: str = Field(default="0.0.0.0", description="Bind address for service")
    advertise_address: str | None = Field(default=None, description="Advertised address (auto-detect if None)")

    # Security settings
    enable_tls: bool = Field(default=False, description="Enable TLS for service communication")
    tls_cert_path: str | None = Field(default=None, description="TLS certificate path")
    tls_key_path: str | None = Field(default=None, description="TLS private key path")

    # Monitoring and metrics
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9090, description="Metrics endpoint port")

    # Environment-specific settings
    environment: str = Field(default="development", description="Deployment environment")
    datacenter: str = Field(default="local", description="Datacenter identifier")
    region: str = Field(default="us-east-1", description="Region identifier")

    @validator("registry_backend")
    def validate_registry_backend(cls, v):
        valid_backends = ["redis", "consul", "etcd", "memory"]
        if v not in valid_backends:
            raise ValueError(f"Registry backend must be one of: {valid_backends}")
        return v

    @validator("bind_address")
    def validate_bind_address(cls, v):
        # Basic IP address validation
        if v not in ["0.0.0.0", "127.0.0.1", "localhost"] and not v.replace(".", "").isdigit():
            raise ValueError("Invalid bind address format")
        return v

    @classmethod
    def from_env(cls) -> ServiceDiscoveryConfig:
        """Create configuration from environment variables."""
        env_config = {}

        # Map environment variables to config fields
        env_mapping = {
            "HIVE_SERVICE_REGISTRY_BACKEND": "registry_backend",
            "HIVE_SERVICE_REGISTRY_URL": "registry_url",
            "HIVE_SERVICE_TTL": "service_ttl",
            "HIVE_SERVICE_BIND_ADDRESS": "bind_address",
            "HIVE_SERVICE_ADVERTISE_ADDRESS": "advertise_address",
            "HIVE_SERVICE_ENVIRONMENT": "environment",
            "HIVE_SERVICE_DATACENTER": "datacenter",
            "HIVE_SERVICE_REGION": "region",
            "HIVE_SERVICE_ENABLE_TLS": "enable_tls",
            "HIVE_SERVICE_HEALTH_CHECK_INTERVAL": "health_check.interval",
            "HIVE_SERVICE_DISCOVERY_INTERVAL": "discovery_interval",
            "HIVE_SERVICE_LB_STRATEGY": "load_balancer.strategy",
        }

        for env_var, config_path in env_mapping.items():
            if env_value := os.getenv(env_var):
                # Handle nested config paths
                if "." in config_path:
                    parent, child = config_path.split(".", 1)
                    if parent not in env_config:
                        env_config[parent] = {}

                    # Convert value types
                    if config_path.endswith((".interval", ".timeout", ".delay")):
                        env_config[parent][child] = float(env_value)
                    elif config_path.endswith((".ttl", ".threshold", ".attempts", ".port")):
                        env_config[parent][child] = int(env_value)
                    elif config_path.endswith(".enabled"):
                        env_config[parent][child] = env_value.lower() in ("true", "1", "yes")
                    else:
                        env_config[parent][child] = (env_value,)
                else:
                    # Handle direct config fields
                    if config_path in ["service_ttl", "metrics_port"]:
                        env_config[config_path] = int(env_value)
                    elif config_path in ["discovery_interval", "registration_retry_delay"]:
                        env_config[config_path] = float(env_value)
                    elif config_path == "enable_tls":
                        env_config[config_path] = env_value.lower() in ("true", "1", "yes")
                    else:
                        env_config[config_path] = env_value

        return cls(**env_config)

    def get_service_tags(self, additional_tags: list[str] = None) -> list[str]:
        """Get standard service tags with optional additional tags."""
        tags = [
            f"environment:{self.environment}",
            f"datacenter:{self.datacenter}",
            f"region:{self.region}",
            "version:1.0.0",
            "platform:hive",
        ]

        if additional_tags:
            tags.extend(additional_tags)

        return tags

    def get_health_check_url(self, service_host: str, service_port: int) -> str:
        """Generate health check URL for a service."""
        protocol = "https" if self.enable_tls else "http"
        return f"{protocol}://{service_host}:{service_port}{self.health_check.http_path}"
