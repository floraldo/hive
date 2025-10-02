"""Base FastAPI application with Hive platform standards."""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hive_logging import get_logger

from ..config.app_config import HiveAppConfig
from .health import add_health_endpoints
from .metrics import add_metrics_endpoints
from .middleware import add_error_handling_middleware, add_logging_middleware, add_performance_middleware

logger = get_logger(__name__)


class HiveApp:
    """
    Enhanced FastAPI application with Hive platform standards.

    Provides production-grade foundation with:
    - Health monitoring endpoints
    - Prometheus metrics integration
    - Structured logging
    - Error handling
    - CORS configuration
    - Performance monitoring
    """

    def __init__(
        self,
        title: str,
        description: str,
        version: str = "1.0.0",
        config: HiveAppConfig | None = None,
    ) -> None:
        """Initialize Hive application."""
        self.config = config or HiveAppConfig()

        self.app = FastAPI(
            title=title,
            description=description,
            version=version,
            docs_url="/api/docs" if self.config.api.enable_docs else None,
            redoc_url="/api/redoc" if self.config.api.enable_docs else None,
            openapi_url="/api/openapi.json" if self.config.api.enable_docs else None,
        )

        self._setup_middleware()
        self._setup_endpoints()

        logger.info(f"HiveApp '{title}' v{version} initialized")

    def _setup_middleware(self) -> None:
        """Setup standard middleware stack."""
        # CORS middleware
        if self.config.api.enable_cors:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=self.config.api.cors_origins,
                allow_credentials=self.config.api.cors_credentials,
                allow_methods=self.config.api.cors_methods,
                allow_headers=self.config.api.cors_headers,
            )

        # Custom middleware (order matters - last added runs first)
        add_performance_middleware(self.app, self.config)
        add_error_handling_middleware(self.app, self.config)
        add_logging_middleware(self.app, self.config)

    def _setup_endpoints(self) -> None:
        """Setup standard endpoints."""
        # Health endpoints for Kubernetes
        add_health_endpoints(self.app, self.config)

        # Metrics endpoints for Prometheus
        if self.config.monitoring.enable_metrics:
            add_metrics_endpoints(self.app, self.config)

    def get_app(self) -> FastAPI:
        """Get the underlying FastAPI application."""
        return self.app


def create_hive_app(
    title: str,
    description: str,
    version: str = "1.0.0",
    config: HiveAppConfig | None = None,
    cost_calculator: Any | None = None,
    daily_cost_limit: float = 100.0,
    monthly_cost_limit: float = 2000.0,
    rate_limits: dict[str, int] | None = None,
    enable_cors: bool = False,
    enable_metrics: bool = True,
    **kwargs: Any,
) -> FastAPI:
    """
    Create a production-ready FastAPI application with Hive standards.

    Args:
        title: Application title (required),
        description: Application description (required),
        version: Application version,
        config: Configuration object (optional, will create default),
        cost_calculator: Custom cost calculator for tracking,
        daily_cost_limit: Daily cost limit in USD,
        monthly_cost_limit: Monthly cost limit in USD,
        rate_limits: Rate limiting configuration,
        enable_cors: Enable CORS middleware,
        enable_metrics: Enable Prometheus metrics,
        **kwargs: Additional FastAPI kwargs

    Returns:
        Configured FastAPI application

    Raises:
        ValueError: If required parameters are invalid,
        RuntimeError: If application initialization fails

    Example:
        ```python
        from hive_app_toolkit import create_hive_app

        app = create_hive_app(
            title="My Service",
            description="Production-ready service",
            daily_cost_limit=50.0,
            rate_limits={"per_minute": 30},
            enable_cors=True
        )

        @app.get("/api/hello")
        async def hello():
            return {"message": "Hello, Hive!"}
        ```
    """
    # Input validation
    if not title or not isinstance(title, str):
        raise ValueError("title must be a non-empty string")

    if not description or not isinstance(description, str):
        raise ValueError("description must be a non-empty string")

    if not version or not isinstance(version, str):
        raise ValueError("version must be a non-empty string")

    if daily_cost_limit <= 0:
        raise ValueError("daily_cost_limit must be positive")

    if monthly_cost_limit <= 0:
        raise ValueError("monthly_cost_limit must be positive")

    try:
        logger.info(f"Creating Hive app: {title} v{version}")

        # Create enhanced configuration if not provided
        if config is None:
            config = HiveAppConfig()

        # Apply toolkit parameters to config
        if enable_cors:
            config.api.enable_cors = True

        if not enable_metrics:
            config.monitoring.enable_metrics = False

        # Create the application
        hive_app = HiveApp(title=title, description=description, version=version, config=config)

        app = hive_app.get_app()

        # Apply any additional FastAPI configuration safely
        for key, value in kwargs.items():
            if hasattr(app, key):
                try:
                    setattr(app, key, value)
                    logger.debug(f"Applied FastAPI config: {key}={value}")
                except Exception as e:
                    logger.warning(f"Failed to set FastAPI attribute {key}: {e}")
            else:
                logger.warning(f"Unknown FastAPI attribute: {key}")

        logger.info(f"✓ Hive app created successfully: {title}")
        return app

    except Exception as e:
        error_msg = f"Failed to create Hive app '{title}': {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
