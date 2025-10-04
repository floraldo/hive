"""Configuration for hive-architect."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class HiveArchitectConfig(BaseModel):
    """Configuration for hive-architect."""

    # Application settings
    app_name: str = Field(default="hive-architect", description="Application name")
    version: str = Field(default="0.1.0", description="Application version")
    environment: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development"),
        description="Environment (development, staging, production)",
    )
    # API settings
    host: str = Field(
        default_factory=lambda: os.getenv("HOST", "127.0.0.1"),
        description="API host",
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("PORT", "8000")),
        description="API port",
    )
    # Logging settings
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"),
        description="Logging level",
    )
    # Database settings
    database_path: str = Field(
        default_factory=lambda: os.getenv("DATABASE_PATH", "data/hive-architect.db"),
        description="Database file path",
    )
    # Cache settings
    cache_enabled: bool = Field(
        default_factory=lambda: os.getenv("CACHE_ENABLED", "true").lower() == "true",
        description="Enable caching",
    )
    cache_ttl: int = Field(
        default_factory=lambda: int(os.getenv("CACHE_TTL", "3600")),
        description="Cache TTL in seconds",
    )
    # Cost limits
    daily_cost_limit: float = Field(
        default=(100.0,),
        description="Daily cost limit in USD",
    )
    monthly_cost_limit: float = Field(
        default=(2000.0,),
        description="Monthly cost limit in USD",
    )
    per_operation_limit: float = Field(
        default=1.0,
        description="Per-operation cost limit in USD",
    )

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
