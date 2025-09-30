"""
Centralized configuration management for EcoSystemiser platform.,

Combines all configuration needs for the modular architecture including
profile_loader (climate, demand), solver, analyser, and reporting modules.
"""

from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

from functools import lru_cache
from pathlib import Path
from typing import Any

# Pydantic v2 imports
from pydantic import ConfigDict, Field, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    """Database configuration"""

    url: str | None = None
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    name: str = Field(default="ecosystemiser")
    user: str = Field(default="postgres")
    password: str | None = None

    @field_validator("url", mode="before")
    @classmethod
    def build_url_if_needed(cls, v: Any, info: Any) -> str | None:
        if v is None and info.data.get("password"):
            return f"postgresql://{info.data.get('user', 'postgres')}:{info.data['password']}@{info.data.get('host', 'localhost')}:{info.data.get('port', 5432)}/{info.data.get('name', 'ecosystemiser')}"
        return v

    class Config:
        env_prefix = "ECOSYSTEMISER_DB_"


class HTTPSettings(BaseSettings):
    """HTTP client configuration"""

    timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_backoff_factor: float = Field(default=0.5, ge=0.1, le=5.0)
    connection_pool_size: int = Field(default=10, ge=1, le=100)
    keepalive_expiry: int = Field(default=30, ge=5, le=300)

    class Config:
        env_prefix = "ECOSYSTEMISER_HTTP_"


class CacheSettings(BaseSettings):
    """Cache configuration"""

    # Memory cache
    memory_size: int = Field(default=100, ge=10, le=10000)
    memory_ttl: int = Field(default=300, ge=60, le=3600)

    # Disk cache
    cache_dir: Path = Field(default=Path("/tmp/ecosystemiser_cache"))
    disk_size_mb: int = Field(default=1000, ge=100, le=10000)
    disk_ttl: int = Field(default=3600, ge=300, le=86400)

    # Redis cache (optional)
    redis_url: str | None = Field(default=None)
    redis_ttl: int = Field(default=86400, ge=3600, le=604800)
    redis_key_prefix: str = Field(default="ecosystemiser:")

    @field_validator("cache_dir")
    @classmethod
    def ensure_cache_dir_exists(cls, v):
        v.mkdir(parents=True, exist_ok=True)
        return v

    class Config:
        env_prefix = "ECOSYSTEMISER_CACHE_"


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration"""

    requests_per_minute: int = Field(default=60, ge=1, le=1000)
    burst_size: int = Field(default=10, ge=1, le=100)

    class Config:
        env_prefix = "ECOSYSTEMISER_RATELIMIT_"


class JobQueueSettings(BaseSettings):
    """Job queue configuration"""

    redis_url: str = Field(default="redis://localhost:6379")
    max_jobs: int = Field(default=1000, ge=100, le=10000)
    job_timeout: int = Field(default=3600, ge=60, le=86400)
    result_ttl: int = Field(default=86400, ge=3600, le=604800)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: int = Field(default=60, ge=10, le=600)

    # Worker settings
    worker_concurrency: int = Field(default=4, ge=1, le=20)
    worker_heartbeat: int = Field(default=30, ge=10, le=60)

    class Config:
        env_prefix = "ECOSYSTEMISER_QUEUE_"


class ObservabilitySettings(BaseSettings):
    """Observability configuration"""

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json", pattern="^(json|console)$")
    log_correlation_id: bool = Field(default=True)

    # Metrics
    metrics_enabled: bool = Field(default=True)
    metrics_port: int = Field(default=9090, ge=1024, le=65535)
    metrics_path: str = Field(default="/metrics")

    # Tracing
    tracing_enabled: bool = Field(default=True)
    tracing_service_name: str = Field(default="ecosystemiser")
    tracing_endpoint: str | None = Field(default=None)
    tracing_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)

    class Config:
        env_prefix = "ECOSYSTEMISER_OBSERVABILITY_"


class APISettings(BaseSettings):
    """API configuration"""

    title: str = Field(default="EcoSystemiser Platform API")
    description: str = Field(default="Modular platform for climate, demand, and optimization")
    version: str = Field(default="3.0.0")

    # Versioning
    api_prefix: str = Field(default="/api")
    default_version: str = Field(default="v3")
    supported_versions: list[str] = Field(default=["v2", "v3"])

    # CORS
    cors_origins: list[str] = Field(default=["*"])
    cors_methods: list[str] = Field(default=["*"])
    cors_headers: list[str] = Field(default=["*"])

    # Limits
    max_batch_size: int = Field(default=100, ge=1, le=1000)
    max_streaming_chunk_size: int = Field(default=10000, ge=100, le=100000)
    request_timeout: int = Field(default=300, ge=30, le=3600)

    class Config:
        env_prefix = "ECOSYSTEMISER_API_"


class ProfileLoaderSettings(BaseSettings):
    """Profile Loader module configuration"""

    # Climate Adapters
    nasa_power_enabled: bool = Field(default=True)
    nasa_power_base_url: str = Field(default="https://power.larc.nasa.gov/api/temporal")
    nasa_power_rate_limit: int = Field(default=60)
    nasa_power_chunk_days: int = Field(default=365)

    meteostat_enabled: bool = Field(default=True)
    meteostat_api_key: str | None = Field(default=None)
    meteostat_rate_limit: int = Field(default=100)

    era5_enabled: bool = Field(default=True)
    era5_api_key: str | None = Field(default=None)
    era5_api_url: str = Field(default="https://cds.climate.copernicus.eu/api/v2")

    pvgis_enabled: bool = Field(default=True)
    pvgis_base_url: str = Field(default="https://re.jrc.ec.europa.eu/api/v5_2")
    pvgis_rate_limit: int = Field(default=30)

    epw_enabled: bool = Field(default=True)
    epw_data_dir: Path = Field(default=Path("/data/epw"))

    # Processing defaults
    preprocessing_enabled: bool = Field(default=True)
    postprocessing_enabled: bool = Field(default=False)

    # Quality control
    qc_enabled: bool = Field(default=True)
    qc_strict_mode: bool = Field(default=False)
    qc_max_missing_percent: float = Field(default=20.0)

    # Gap filling
    gap_fill_enabled: bool = Field(default=True)
    gap_fill_max_hours: int = Field(default=24)
    gap_fill_method: str = Field(default="smart")

    @field_validator("epw_data_dir")
    @classmethod
    def ensure_epw_dir_exists(cls, v):
        v.mkdir(parents=True, exist_ok=True)
        return v

    class Config:
        env_prefix = "ECOSYSTEMISER_PROFILE_"


class SolverSettings(BaseSettings):
    """Solver module configuration (placeholder)"""

    enabled: bool = Field(default=False)
    max_iterations: int = Field(default=1000)
    convergence_tolerance: float = Field(default=1e-6)

    class Config:
        env_prefix = "ECOSYSTEMISER_SOLVER_"


class AnalyserSettings(BaseSettings):
    """Analyser module configuration (placeholder)"""

    enabled: bool = Field(default=False)

    class Config:
        env_prefix = "ECOSYSTEMISER_ANALYSER_"


class ReportingSettings(BaseSettings):
    """Reporting module configuration (placeholder)"""

    enabled: bool = Field(default=False)
    output_dir: Path = Field(default=Path("/data/reports"))

    @field_validator("output_dir")
    @classmethod
    def ensure_output_dir_exists(cls, v):
        v.mkdir(parents=True, exist_ok=True)
        return v

    class Config:
        env_prefix = "ECOSYSTEMISER_REPORTING_"


class FeatureFlags(BaseSettings):
    """Feature flags for gradual rollout"""

    enable_streaming: bool = Field(default=True)
    enable_batch_processing: bool = Field(default=True)
    enable_async_jobs: bool = Field(default=True)
    enable_caching: bool = Field(default=True)
    enable_rate_limiting: bool = Field(default=True)
    enable_correlation_ids: bool = Field(default=True)
    enable_schema_validation: bool = Field(default=True)
    enable_adapter_plugins: bool = Field(default=False)

    class Config:
        env_prefix = "ECOSYSTEMISER_FEATURE_"


class Settings(BaseSettings):
    """Main settings container for EcoSystemiser platform"""

    # Environment
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = Field(default=False)
    testing: bool = Field(default=False)

    # Database
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # Core configurations
    http: HTTPSettings = Field(default_factory=HTTPSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    queue: JobQueueSettings = Field(default_factory=JobQueueSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    api: APISettings = Field(default_factory=APISettings)

    # Module configurations
    profile_loader: ProfileLoaderSettings = Field(default_factory=ProfileLoaderSettings)
    solver: SolverSettings = Field(default_factory=SolverSettings)
    analyser: AnalyserSettings = Field(default_factory=AnalyserSettings)
    reporting: ReportingSettings = Field(default_factory=ReportingSettings)

    # Feature flags
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v, info):
        """Adjust settings based on environment"""
        if v == "production":
            # Enforce production settings
            if "debug" in info.data:
                info.data["debug"] = False
        return v

    def get_adapter_config(self, adapter_name: str) -> dict[str, Any]:
        """Get configuration for a specific adapter"""
        config = {}
        prefix = f"{adapter_name}_"

        for field_name, field_value in self.profile_loader.dict().items():
            if field_name.startswith(prefix):
                key = field_name[len(prefix) :]
                config[key] = field_value

        return config

    def is_adapter_enabled(self, adapter_name: str) -> bool:
        """Check if an adapter is enabled"""
        field_name = f"{adapter_name}_enabled"
        return getattr(self.profile_loader, field_name, False)

    def get_cache_config(self):
        """Get cache configuration for adapters"""
        from ecosystemiser.profile_loader.climate.config_models import CacheConfig

        return CacheConfig(
            memory_size=self.cache.memory_size,
            memory_ttl=self.cache.memory_ttl,
            cache_dir=str(self.cache.cache_dir),
            disk_ttl=self.cache.disk_ttl,
            redis_url=self.cache.redis_url,
            redis_ttl=self.cache.redis_ttl,
        )

    def get_http_config(self):
        """Get HTTP configuration for adapters"""
        from ecosystemiser.profile_loader.climate.config_models import HTTPConfig

        return HTTPConfig(
            timeout=self.http.timeout,
            max_retries=self.http.max_retries,
            retry_backoff_factor=self.http.retry_backoff_factor,
            connection_pool_size=self.http.connection_pool_size,
            keepalive_expiry=self.http.keepalive_expiry,
        )

    def get_rate_limit_config(self):
        """Get rate limit configuration for adapters"""
        # Import here to avoid circular dependency
        from ecosystemiser.profile_loader.climate.config_models import RateLimitConfig

        return RateLimitConfig(
            requests_per_minute=self.rate_limit.requests_per_minute,
            burst_size=self.rate_limit.burst_size,
        )

    model_config = ConfigDict(
        env_prefix="ECOSYSTEMISER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Allow extra environment variables
    )


# Singleton instance
_settings: Settings | None = None


@lru_cache
def get_settings() -> Settings:
    """Get singleton settings instance"""
    global _settings

    if _settings is None:
        _settings = Settings()

    return _settings


def reload_settings() -> Settings:
    """Force reload settings (useful for testing)"""
    global _settings
    get_settings.cache_clear()
    _settings = Settings()
    return _settings


# Convenience exports
settings = get_settings()
