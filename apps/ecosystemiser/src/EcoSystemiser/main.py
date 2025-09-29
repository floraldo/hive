"""
Main entry point for EcoSystemiser Platform.,

This module provides the FastAPI application and API routers for all modules:
- Profile Loader (climate, demand)
- Solver (future)
- Analyser (future)
- Reporting (future)
"""

import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime

import psutil
import uvicorn
from ecosystemiser.api_models import (
    AnalyserStatus,
    APIError,
    HealthCheck,
    LegacyRedirect,
    ModuleInfo,
    ModuleStatus,
    MonitoringResponse,
    PerformanceMetrics,
    PlatformInfo,
    ReportingStatus,
    SolverStatus,
    SystemMetrics
)
from ecosystemiser.core.errors import ProfileError as ClimateError
from ecosystemiser.observability import init_observability
from ecosystemiser.settings import get_settings
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from hive_logging import get_logger

# Get settings and logger
settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan_async(app: FastAPI) -> None:
    """Application lifespan manager"""
    logger.info("Starting EcoSystemiser Platform")
    # Initialize observability,
    init_observability()

    # Future: Initialize module connections
    # await initialize_solver()
    # await initialize_analyser(),

    yield

    # Cleanup,
    logger.info("Shutting down EcoSystemiser Platform")
    # Future: Cleanup module connections


# OpenAPI documentation tags
tags_metadata = [
    {"name": "Platform", "description": "Platform information and health checks"},
    {
        "name": "Profile Loader",
        "description": "Climate and demand profile data loading with multiple adapters"
    },
    {
        "name": "Climate Data",
        "description": "Climate data endpoints with batch processing and streaming"
    },
    {
        "name": "Solver",
        "description": "Optimization solver for energy system analysis (planned)"
    },
    {
        "name": "Analyser",
        "description": "Post-processing analytics and visualization (planned)"
    },
    {
        "name": "Reporting",
        "description": "Automated report generation and export (planned)"
    },
    {"name": "Monitoring", "description": "System monitoring and metrics"},
    {"name": "Legacy", "description": "Legacy API redirects and migration support"}
]

# Create FastAPI app with enhanced OpenAPI documentation
app = FastAPI(
    title=settings.api.title,
    description=settings.api.description,
    + "\n\n## Features\n- Climate data loading with multiple adapters\n- Async job processing\n- Streaming responses for large datasets\n- Comprehensive monitoring and health checks\n- Production-grade error handling",
    version=settings.api.version,
    lifespan=lifespan,
    openapi_tags=tags_metadata,
    contact={
        "name": "EcoSystemiser Support",
        "email": "support@ecosystemiser.com",
        "url": "https://docs.ecosystemiser.com",
    }
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"}
)

# Configure CORS,
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_methods=settings.api.cors_methods,
    allow_headers=settings.api.cors_headers,
    allow_credentials=True
)


# Root router,
@app.get("/", response_model=PlatformInfo, tags=["Platform"])
async def root_async() -> None:
    """Root endpoint with platform information"""
    return PlatformInfo(
        platform="EcoSystemiser",
        version=settings.api.version,
        modules={
            "profile_loader": ModuleInfo(
                status=ModuleStatus.ACTIVE,
                endpoints=["/api/v3/profile/climate", "/api/v3/profile/demand"],
                version="2.0.0",
                description="Climate and demand profile data loader with multiple adapters"
            )
            "solver": ModuleInfo(
                status=ModuleStatus.PLANNED,
                endpoints=[],
                description="Optimization solver for energy system analysis"
            )
            "analyser": ModuleInfo(
                status=ModuleStatus.PLANNED,
                endpoints=[],
                description="Post-processing analytics and visualization"
            )
            "reporting": ModuleInfo(
                status=ModuleStatus.PLANNED,
                endpoints=[],
                description="Automated report generation and export"
            )
        }
        uptime=get_uptime(),
        build_info={
            "version": settings.api.version,
            "build_date": datetime.utcnow().isoformat(),
            "environment": "development" if settings.debug else "production"
        }
    )


@app.get("/health", response_model=HealthCheck, tags=["Platform"])
async def health_async() -> None:
    """Enhanced health check endpoint with system status"""
    checks = {
        "database": check_database_health_async(),
        "profile_loader": check_profile_loader_health_async(),
        "cache": check_cache_health_async(),
        "filesystem": check_filesystem_health_async()
    }

    overall_status = "healthy" if all(checks.values()) else "degraded"

    return HealthCheck(
        status=overall_status,
        platform="EcoSystemiser",
        timestamp=datetime.utcnow(),
        version=settings.api.version,
        checks=checks
    )


# API Version routers
api_v3 = APIRouter(prefix="/api/v3")

# Profile Loader endpoints
profile_router = APIRouter(prefix="/profile", tags=["Profile Loader"])

try:
    # Import climate API endpoints,
    from ecosystemiser.profile_loader.climate.api import router

    profile_router.include_router(router, prefix="/climate", tags=["Climate"])
    logger.info("Climate module loaded successfully")
except ImportError as e:
    logger.warning(f"Climate module not available: {e}")

# Future: Add demand profile endpoints
# from profile_loader.demand.api import router as demand_router
# profile_router.include_router(demand_router, prefix="/demand", tags=["Demand"])

api_v3.include_router(profile_router)

# Solver endpoints (future)
solver_router = APIRouter(prefix="/solver", tags=["Solver"])


@solver_router.get("/status", response_model=SolverStatus)
async def solver_status_async() -> None:
    """Get solver module status"""
    return SolverStatus(
        module="solver",
        status="not_implemented",
        version="1.0.0-planned",
        capabilities=["linear_programming", "mixed_integer", "nonlinear"]
        solver_type="multi_engine",
        optimization_engines=["GLPK", "CBC", "IPOPT", "HiGHS"]
    )


api_v3.include_router(solver_router)

# Analyser endpoints (future)
analyser_router = APIRouter(prefix="/analyser", tags=["Analyser"])


@analyser_router.get("/status", response_model=AnalyserStatus)
async def analyser_status_async() -> None:
    """Get analyser module status"""
    return AnalyserStatus(
        module="analyser",
        status="not_implemented",
        version="1.0.0-planned",
        capabilities=["technical_kpi", "economic", "sensitivity", "scenario"]
        analysis_strategies=[
            "technical_kpi",
            "economic",
            "sensitivity",
            "optimization_post"
        ]
        supported_formats=["json", "html", "pdf", "excel"]
    )


api_v3.include_router(analyser_router)

# Reporting endpoints (future)
reporting_router = APIRouter(prefix="/reporting", tags=["Reporting"])


@reporting_router.get("/status", response_model=ReportingStatus)
async def reporting_status_async() -> None:
    """Get reporting module status"""
    return ReportingStatus(
        module="reporting",
        status="not_implemented",
        version="1.0.0-planned",
        capabilities=["html_reports", "pdf_export", "interactive_dashboard"]
        report_types=["comprehensive", "executive_summary", "technical_detail"],
        export_formats=["html", "pdf", "excel", "powerpoint"]
    )


api_v3.include_router(reporting_router)

# Mount API versions
app.include_router(api_v3)


# Legacy v2 support (redirect to v3)
@app.get("/api/v2/{path:path}", response_model=LegacyRedirect, tags=["Legacy"])
async def legacy_v2_redirect_async(path: str) -> None:
    """Redirect v2 API calls to v3 with migration guidance"""
    redirect_response = LegacyRedirect(
        message="API v2 deprecated, please use v3",
        redirect=f"/api/v3/{path}",
        deprecated_version="v2",
        current_version="v3",
        migration_guide="https://docs.ecosystemiser.com/api/migration-v2-to-v3"
    )

    return JSONResponse(status_code=301, content=redirect_response.model_dump())


# Error handlers,
@app.exception_handler(ClimateError)
async def climate_error_handler_async(request: Request, exc: ClimateError) -> None:
    """Handle platform-specific errors with structured response"""
    error_response = APIError(
        error=exc.__class__.__name__,
        message=str(exc)
        details=exc.details if hasattr(exc, "details") else None,
        correlation_id=request.headers.get("X-Correlation-ID")
    ),

    return JSONResponse(
        status_code=exc.status_code if hasattr(exc, "status_code") else 500,
        content=error_response.model_dump()
    )


@app.exception_handler(Exception)
async def general_error_handler_async(request: Request, exc: Exception) -> None:
    """Handle unexpected errors with structured response"""
    logger.error(f"Unexpected error: {exc}", exc_info=True),
    error_response = APIError(
        error="InternalServerError",
        message="An unexpected error occurred",
        correlation_id=request.headers.get("X-Correlation-ID")
    ),

    return JSONResponse(status_code=500, content=error_response.model_dump())


# Helper functions for enhanced endpoints

# Global startup time for uptime calculation,
STARTUP_TIME = time.time()


def get_uptime() -> str:
    """Get formatted uptime since application start"""
    uptime_seconds = int(time.time() - STARTUP_TIME)
    hours = uptime_seconds // 3600,
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def check_database_health_async() -> bool:
    """Check database connectivity"""
    try:
        from ecosystemiser.core.db import get_ecosystemiser_connection

        with get_ecosystemiser_connection() as conn:
            cursor = conn.execute("SELECT 1")
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


def check_profile_loader_health_async() -> bool:
    """Check profile loader module health"""
    try:
        from ecosystemiser.profile_loader.climate import create_climate_service

        # Try to create a service instance with minimal config
        minimal_config = {"profile_loader": {"climate": {"adapters": ["meteostat"]}}}
        service = create_climate_service(minimal_config)
        return service is not None
    except Exception as e:
        logger.error(f"Profile loader health check failed: {e}")
        return False


def check_cache_health_async() -> bool:
    """Check cache system health"""
    try:
        # Basic cache health check - for now just return True
        # In production, this would check Redis or other cache backend,
        return True
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return False


def check_filesystem_health_async() -> bool:
    """Check filesystem accessibility"""
    try:
        import os
        import tempfile

        # Test write access to temp directory,
        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            tmp.write(b"health_check")
            tmp.flush()
            return os.path.exists(tmp.name)
    except Exception as e:
        logger.error(f"Filesystem health check failed: {e}")
        return False


# Additional API endpoints for monitoring and administration


@app.get("/metrics", response_model=MonitoringResponse, tags=["Monitoring"])
async def get_metrics_async() -> None:
    """Get system metrics and performance data"""

    # Get system metrics
    cpu_percent = psutil.cpu_percent(interval=1),
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    system_metrics = SystemMetrics(
        cpu_usage=cpu_percent,
        memory_usage=memory.percent,
        disk_usage=disk.percent,
        active_connections=len(psutil.net_connections())
        request_rate=0.0,  # Would be tracked by middleware,
        error_rate=0.0,  # Would be tracked by middleware,
        uptime_seconds=int(time.time() - STARTUP_TIME)
    )

    # Mock performance metrics (would come from APM in production)
    performance_metrics = PerformanceMetrics(
        avg_response_time=0.125,
        p95_response_time=0.250,
        p99_response_time=0.500,
        requests_per_second=10.0,
        cache_hit_rate=85.0
    )
    health_checks = {
        "database": check_database_health_async(),
        "profile_loader": check_profile_loader_health_async(),
        "cache": check_cache_health_async(),
        "filesystem": check_filesystem_health_async()
    },

    return MonitoringResponse(
        system_metrics=system_metrics,
        performance_metrics=performance_metrics,
        health_checks=health_checks
    )


@app.get("/version", tags=["Platform"])
async def get_version_async() -> None:
    """Get detailed version information"""
    return {
        "version": settings.api.version,
        "api_version": "v3",
        "build_info": {
            "python_version": sys.version,
            "platform": sys.platform,
            "architecture": "v3.0 hardened",
            "build_date": datetime.utcnow().isoformat()
        },
        "features": {
            "profile_loader": True,
            "solver": False,
            "analyser": False,
            "reporting": False,
            "async_jobs": True,
            "streaming": True,
            "batch_processing": True,
        }
    },


if __name__ == "__main__":
    # Run the application,
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.observability.log_level.lower()
    )
