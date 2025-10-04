"""FastAPI application for hive-architect."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hive_logging import get_logger

from ..config import HiveArchitectConfig
from .health import router as health_router

logger = get_logger(__name__)


def create_app(config: HiveArchitectConfig | None = None) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        config: Application configuration (optional, uses default if None)

    Returns:
        Configured FastAPI application
    """
    config = config or HiveArchitectConfig()

    app = FastAPI(
        title="hive-architect",
        description="hive-architect - Hive platform service",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(health_router, prefix="/health", tags=["health"])

    @app.on_event("startup")
    async def startup() -> None:
        """Startup event handler."""
        logger.info("hive-architect starting up...")
        logger.info(f"Environment: {config.environment}")
        logger.info(f"Version: {config.version}")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        """Shutdown event handler."""
        logger.info("hive-architect shutting down...")

    return app
