"""
Main application entry point for the refactored climate platform.

Initializes all components with the new architecture:
- Centralized configuration
- Service layer
- Structured logging
- Observability
- API versioning
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from EcoSystemiser.settings import get_settings
from .logging_config import setup_logging, get_logger
from EcoSystemiser.observability import init_observability, shutdown_observability

# Initialize logging first
setup_logging()
logger = get_logger(__name__)

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown tasks.
    """
    # Startup
    logger.info(
        "Starting EcoSystemiser Climate Platform",
        version=settings.api.version,
        environment=settings.environment
    )
    
    # Initialize observability
    if settings.observability.metrics_enabled or settings.observability.tracing_enabled:
        init_observability()
        logger.info("Observability initialized")
    
    # Initialize job service
    from .services.job_service import JobService
    job_service = JobService()
    await job_service.initialize()
    logger.info("Job service initialized")
    
    # Store services in app state for access in endpoints
    app.state.job_service = job_service
    app.state.settings = settings
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Close job service
    if hasattr(app.state, 'job_service'):
        await app.state.job_service.close()
    
    # Shutdown observability
    shutdown_observability()
    
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI app
    """
    # Create app with lifespan manager
    app = FastAPI(
        title=settings.api.title,
        description=settings.api.description,
        version=settings.api.version,
        lifespan=lifespan,
        docs_url=None,  # Disable default docs
        redoc_url=None,  # Disable default redoc
        openapi_url=None  # Disable default openapi
    )
    
    # Add middleware
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_methods=settings.api.cors_methods,
        allow_headers=settings.api.cors_headers,
        allow_credentials=True
    )
    
    # Add custom middleware for correlation IDs
    @app.middleware("http")
    async def correlation_id_middleware(request, call_next):
        """Add correlation ID to requests"""
        from ...errors import CorrelationIDMiddleware
        from .logging_config import set_correlation_id, clear_context
        
        # Get or create correlation ID
        correlation_id = CorrelationIDMiddleware.get_or_create_correlation_id(
            dict(request.headers)
        )
        
        # Set in logging context
        set_correlation_id(correlation_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Add correlation ID to response
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
        finally:
            # Clear logging context
            clear_context()
    
    # Add versioned routers
    # TODO: Implement create_versioned_app or remove this line
    # app = create_versioned_app(app)
    
    # Add version-specific documentation
    for version in settings.api.supported_versions:
        # Enable docs for each version
        docs_url = f"{settings.api.api_prefix}/{version}/docs"
        redoc_url = f"{settings.api.api_prefix}/{version}/redoc"
        openapi_url = f"{settings.api.api_prefix}/{version}/openapi.json"
        
        # This is a simplified approach - in production you'd want
        # separate FastAPI apps or more sophisticated routing
        if version == settings.api.default_version:
            app.docs_url = docs_url
            app.redoc_url = redoc_url
            app.openapi_url = openapi_url
    
    logger.info(
        "Application created",
        supported_versions=settings.api.supported_versions,
        default_version=settings.api.default_version
    )
    
    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    """Run the application with uvicorn"""
    import uvicorn
    
    uvicorn.run(
        "ecosystemiser.profile_loader.climate.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout"
                }
            },
            "root": {
                "level": settings.observability.log_level,
                "handlers": ["default"]
            }
        }
    )