"""Base configuration class for Hive applications."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hive_config import load_config


@dataclass
class APIConfig:
    """API-related configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    enable_docs: bool = True
    enable_cors: bool = True
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    cors_methods: list[str] = field(default_factory=lambda: ["*"])
    cors_headers: list[str] = field(default_factory=lambda: ["*"])
    cors_credentials: bool = True
    max_request_size: int = 16 * 1024 * 1024  # 16MB
    request_timeout: float = 30.0


@dataclass
class DatabaseConfig:
    """Database configuration."""

    enabled: bool = False
    url: str | None = None
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: float = 30.0
    pool_recycle: int = 3600


@dataclass
class CacheConfig:
    """Cache configuration."""

    enabled: bool = True
    url: str | None = None
    ttl_seconds: int = 3600
    max_size_mb: int = 100
    key_prefix: str = "hive"


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""

    enable_metrics: bool = True
    enable_tracing: bool = False
    enable_profiling: bool = False
    metrics_path: str = "/api/metrics"
    health_path: str = "/health"
    log_level: str = "INFO"
    log_format: str = "json"
    enable_request_logging: bool = True


@dataclass
class SecurityConfig:
    """Security configuration."""

    enable_auth: bool = False
    auth_provider: str = "jwt"
    auth_secret_key: str | None = None
    enable_rate_limiting: bool = True
    enable_request_validation: bool = True
    max_request_body_size: int = 16 * 1024 * 1024  # 16MB
    allowed_hosts: list[str] = field(default_factory=list)


@dataclass
class CostControlConfig:
    """Cost control configuration."""

    enabled: bool = True
    hourly_limit: float = 10.0
    daily_limit: float = 100.0
    monthly_limit: float = 2000.0
    per_operation_limit: float = 1.0
    enable_rate_limiting: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000


@dataclass
class HiveAppConfig:
    """
    Comprehensive configuration for Hive applications.

    Provides sensible defaults for production-ready applications
    while allowing customization for specific needs.
    """

    # Application metadata
    app_name: str = "hive-app"
    app_version: str = "1.0.0"
    environment: str = "development"

    # Core components
    api: APIConfig = field(default_factory=APIConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    cost_control: CostControlConfig = field(default_factory=CostControlConfig)

    # Additional configuration
    custom: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Post-initialization setup."""
        # Adjust settings based on environment
        if self.environment == "production":
            self._apply_production_defaults()
        elif self.environment == "development":
            self._apply_development_defaults()

        # Validate configuration
        self._validate_config()

    def _apply_production_defaults(self) -> None:
        """Apply production-optimized defaults."""
        self.api.enable_docs = False  # Disable API docs in production
        self.api.cors_origins = []  # Restrict CORS in production
        self.monitoring.log_level = "INFO"
        self.monitoring.enable_request_logging = False  # Reduce log volume
        self.security.enable_auth = True
        self.security.enable_rate_limiting = True
        self.security.enable_request_validation = True

    def _apply_development_defaults(self) -> None:
        """Apply development-friendly defaults."""
        self.api.enable_docs = True
        self.api.cors_origins = ["*"]
        self.monitoring.log_level = "DEBUG"
        self.monitoring.enable_request_logging = True
        self.security.enable_auth = False
        self.cost_control.daily_limit = 10.0  # Lower limits for dev

    def _validate_config(self) -> None:
        """Validate configuration settings."""
        # API validation
        if self.api.port < 1 or self.api.port > 65535:
            raise ValueError(f"Invalid API port: {self.api.port}")

        if self.api.workers < 1:
            raise ValueError(f"Invalid worker count: {self.api.workers}")

        # Cost control validation
        if self.cost_control.enabled:
            if self.cost_control.daily_limit <= 0:
                raise ValueError(f"Invalid daily limit: {self.cost_control.daily_limit}")

            if self.cost_control.per_operation_limit <= 0:
                raise ValueError(f"Invalid per-operation limit: {self.cost_control.per_operation_limit}")

        # Database validation
        if self.database.enabled and not self.database.url:
            raise ValueError("Database enabled but no URL provided")

    @classmethod
    def load_from_file(cls, config_path: Path) -> "HiveAppConfig":
        """
        Load configuration from file.

        Supports YAML, JSON, and TOML formats.
        """
        config_data = load_config(config_path)
        return cls.from_dict(config_data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HiveAppConfig":
        """Create configuration from dictionary."""
        # Create config instance
        config = cls()

        # Load top-level fields
        for key, value in data.items():
            if key == "api" and isinstance(value, dict):
                config.api = APIConfig(**value)
            elif key == "database" and isinstance(value, dict):
                config.database = DatabaseConfig(**value)
            elif key == "cache" and isinstance(value, dict):
                config.cache = CacheConfig(**value)
            elif key == "monitoring" and isinstance(value, dict):
                config.monitoring = MonitoringConfig(**value)
            elif key == "security" and isinstance(value, dict):
                config.security = SecurityConfig(**value)
            elif key == "cost_control" and isinstance(value, dict):
                config.cost_control = CostControlConfig(**value)
            elif hasattr(config, key):
                setattr(config, key, value)
            else:
                config.custom[key] = value

        return config

    @classmethod
    def from_environment(cls, prefix: str = "HIVE_", config_file: str | None = None) -> "HiveAppConfig":
        """
        Load configuration from environment variables.

        Args:
            prefix: Environment variable prefix,
            config_file: Optional config file path,
        """
        import os

        # Start with defaults or config file
        if config_file and Path(config_file).exists():
            config = cls.load_from_file(Path(config_file))
        else:
            config = cls()

        # Override with environment variables
        env_vars = {k: v for k, v in os.environ.items() if k.startswith(prefix)}

        for env_key, env_value in env_vars.items():
            # Remove prefix and convert to config key
            config_key = env_key[len(prefix) :].lower()

            # Handle nested configuration
            if "." in config_key:
                section, key = config_key.split(".", 1)
                if hasattr(config, section):
                    section_config = getattr(config, section)
                    if hasattr(section_config, key):
                        # Convert string to appropriate type
                        current_value = getattr(section_config, key)
                        converted_value = cls._convert_env_value(env_value, type(current_value))
                        setattr(section_config, key, converted_value)
            else:
                # Top-level configuration
                if hasattr(config, config_key):
                    current_value = getattr(config, config_key)
                    converted_value = cls._convert_env_value(env_value, type(current_value))
                    setattr(config, config_key, converted_value)

        return config

    @staticmethod
    def _convert_env_value(value: str, target_type: type) -> Any:
        """Convert environment variable string to target type."""
        if target_type == bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif target_type == int:
            return int(value)
        elif target_type == float:
            return float(value)
        elif target_type == list:
            return [item.strip() for item in value.split(",")]
        else:
            return value

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "environment": self.environment,
            "api": self.api.__dict__,
            "database": self.database.__dict__,
            "cache": self.cache.__dict__,
            "monitoring": self.monitoring.__dict__,
            "security": self.security.__dict__,
            "cost_control": self.cost_control.__dict__,
            "custom": self.custom,
        }

    def get_uvicorn_config(self) -> dict[str, Any]:
        """Get Uvicorn server configuration."""
        return {
            "host": self.api.host,
            "port": self.api.port,
            "workers": 1 if self.environment == "development" else self.api.workers,
            "log_level": self.monitoring.log_level.lower(),
            "access_log": self.monitoring.enable_request_logging,
        }
