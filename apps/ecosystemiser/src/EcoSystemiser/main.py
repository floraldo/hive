"""
Main entry point for EcoSystemiser Platform.

This module provides the FastAPI application and API routers for all modules:
- Profile Loader (climate, demand)
- Solver (future)
- Analyser (future)
- Reporting (future)
"""

from ecosystemiser.hive_logging_adapter import get_logger

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from contextlib import asynccontextmanager
import sys

from ecosystemiser.settings import get_settings
from ecosystemiser.observability import init_observability, get_logger
from ecosystemiser.core.errors import ProfileError as ClimateError

# Get settings and logger
settings = get_settings()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting EcoSystemiser Platform")
    # Initialize observability
    init_observability()
    
    # Future: Initialize module connections
    # await initialize_solver()
    # await initialize_analyser()
    
    yield
    
    # Cleanup
    logger.info("Shutting down EcoSystemiser Platform")
    # Future: Cleanup module connections

# Create FastAPI app
app = FastAPI(
    title=settings.api.title,
    description=settings.api.description,
    version=settings.api.version,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_methods=settings.api.cors_methods,
    allow_headers=settings.api.cors_headers,
    allow_credentials=True,
)

# Root router
@app.get("/")
async def root():
    """Root endpoint with platform information"""
    return {
        "platform": "EcoSystemiser",
        "version": settings.api.version,
        "modules": {
            "profile_loader": {
                "status": "active",
                "endpoints": ["/api/v3/profile/climate", "/api/v3/profile/demand"]
            },
            "solver": {
                "status": "planned",
                "endpoints": []
            },
            "analyser": {
                "status": "planned",
                "endpoints": []
            },
            "reporting": {
                "status": "planned",
                "endpoints": []
            }
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "platform": "EcoSystemiser"}

# API Version routers
api_v3 = APIRouter(prefix="/api/v3")

# Profile Loader endpoints
profile_router = APIRouter(prefix="/profile", tags=["Profile Loader"])

try:
    # Import climate API endpoints
    from ecosystemiser.profile_loader.climate.api import router
    profile_router.include_router(climate_router, prefix="/climate", tags=["Climate"])
    logger.info("Climate module loaded successfully")
except ImportError as e:
    logger.warning(f"Climate module not available: {e}")

# Future: Add demand profile endpoints
# from profile_loader.demand.api import router as demand_router
# profile_router.include_router(demand_router, prefix="/demand", tags=["Demand"])

api_v3.include_router(profile_router)

# Solver endpoints (future)
solver_router = APIRouter(prefix="/solver", tags=["Solver"])

@solver_router.get("/status")
async def solver_status():
    """Get solver module status"""
    return {"module": "solver", "status": "not_implemented"}

api_v3.include_router(solver_router)

# Analyser endpoints (future)
analyser_router = APIRouter(prefix="/analyser", tags=["Analyser"])

@analyser_router.get("/status")
async def analyser_status():
    """Get analyser module status"""
    return {"module": "analyser", "status": "not_implemented"}

api_v3.include_router(analyser_router)

# Reporting endpoints (future)
reporting_router = APIRouter(prefix="/reporting", tags=["Reporting"])

@reporting_router.get("/status")
async def reporting_status():
    """Get reporting module status"""
    return {"module": "reporting", "status": "not_implemented"}

api_v3.include_router(reporting_router)

# Mount API versions
app.include_router(api_v3)

# Legacy v2 support (redirect to v3)
@app.get("/api/v2/{path:path}")
async def legacy_v2_redirect(path: str):
    """Redirect v2 API calls to v3"""
    return JSONResponse(
        status_code=301,
        content={"message": "API v2 deprecated, please use v3", "redirect": f"/api/v3/{path}"}
    )

# Error handlers
@app.exception_handler(ClimateError)
async def climate_error_handler(request, exc: ClimateError):
    """Handle platform-specific errors"""
    return JSONResponse(
        status_code=exc.status_code if hasattr(exc, 'status_code') else 500,
        content={
            "error": exc.__class__.__name__,
            "message": str(exc),
            "details": exc.details if hasattr(exc, 'details') else None
        }
    )

@app.exception_handler(Exception)
async def general_error_handler(request, exc: Exception):
    """Handle unexpected errors"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred"
        }
    )

if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.observability.log_level.lower()
    )