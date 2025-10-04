"""FastAPI application for hive-ui."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from hive_logging import get_logger

from ..config import HiveUiConfig
from .health import router as health_router
from .projects import router as projects_router

logger = get_logger(__name__)


def create_app(config: HiveUiConfig | None = None) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        config: Application configuration (optional, uses default if None)

    Returns:
        Configured FastAPI application
    """
    config = config or HiveUiConfig()

    app = FastAPI(
        title="hive-ui",
        description="hive-ui - Hive platform service",
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
    app.include_router(projects_router, prefix="/api", tags=["projects"])

    # Serve static files
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    @app.on_event("startup")
    async def startup() -> None:
        """Startup event handler."""
        logger.info("hive-ui starting up...")
        logger.info(f"Environment: {config.environment}")
        logger.info(f"Version: {config.version}")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        """Shutdown event handler."""
        logger.info("hive-ui shutting down...")

    return app
