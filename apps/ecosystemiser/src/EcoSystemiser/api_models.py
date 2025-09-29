from hive_errors import BaseError
from hive_logging import get_logger

logger = get_logger(__name__)


"""
Comprehensive Pydantic models for EcoSystemiser API.

Provides type-safe request/response models with validation for all API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class ModuleStatus(str, Enum):
    """Module status enumeration"""

    ACTIVE = "active"
    PLANNED = "planned"
    MAINTENANCE = "maintenance"
    DISABLED = "disabled"


class ModuleInfo(BaseModel):
    """Module information model"""

    status: ModuleStatus
    endpoints: List[str] = Field(default_factory=list)
    version: Optional[str] = None
    description: Optional[str] = None


class PlatformInfo(BaseModel):
    """Root endpoint response model"""

    platform: str = Field(default="EcoSystemiser")
    version: str
    modules: Dict[str, ModuleInfo]
    uptime: Optional[str] = None
    build_info: Optional[Dict[str, str]] = None


class HealthCheck(BaseModel):
    """Health check response model"""

    status: str = Field(default="healthy")
    platform: str = Field(default="EcoSystemiser")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: Optional[str] = None
    checks: Optional[Dict[str, bool]] = None


class APIError(BaseError):
    """Standard API error response"""

    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class APIResponse(BaseModel):
    """Standard API response wrapper"""

    success: bool = True
    data: Optional[Any] = None
    error: Optional[APIError] = None
    metadata: Optional[Dict[str, Any]] = None


class ValidationError(BaseError):
    """Validation error details"""

    field: str
    message: str
    invalid_value: Optional[Any] = None


class ServiceStatus(BaseModel):
    """Service status response"""

    module: str
    status: str
    version: Optional[str] = None
    capabilities: Optional[List[str]] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# Solver Module Models
class SolverStatus(ServiceStatus):
    """Solver module status"""

    solver_type: Optional[str] = None
    optimization_engines: Optional[List[str]] = None


class SolverRequest(BaseModel):
    """Solver request model"""

    system_config: Dict[str, Any]
    optimization_targets: List[str]
    constraints: Optional[Dict[str, Any]] = None
    solver_options: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = Field(default=300, ge=10, le=3600)


class SolverResponse(BaseModel):
    """Solver response model"""

    job_id: str
    status: str
    optimal_solution: Optional[Dict[str, Any]] = None
    objective_value: Optional[float] = None
    solve_time: Optional[float] = None
    solver_info: Optional[Dict[str, Any]] = None


# Analyser Module Models
class AnalyserStatus(ServiceStatus):
    """Analyser module status"""

    analysis_strategies: Optional[List[str]] = None
    supported_formats: Optional[List[str]] = None


class AnalysisRequest(BaseModel):
    """Analysis request model"""

    data_path: str
    strategies: Optional[List[str]] = None
    output_format: str = Field(default="json")
    include_plots: bool = Field(default=True)
    correlation_id: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Analysis response model"""

    analysis_id: str
    summary: Dict[str, Any]
    analyses: Dict[str, Any]
    plots: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any]
    processing_time: Optional[float] = None


# Reporting Module Models
class ReportingStatus(ServiceStatus):
    """Reporting module status"""

    report_types: Optional[List[str]] = None
    export_formats: Optional[List[str]] = None


class ReportRequest(BaseModel):
    """Report generation request"""

    analysis_id: str
    report_type: str = Field(default="comprehensive")
    format: str = Field(default="html")
    options: Optional[Dict[str, Any]] = None


class ReportResponse(BaseModel):
    """Report generation response"""

    report_id: str
    download_url: str
    format: str
    size_bytes: Optional[int] = None
    expires_at: Optional[datetime] = None


# Job Management Models (for async operations)
class JobPriority(int, Enum):
    """Job priority levels"""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 10


class JobRequest(BaseModel):
    """Generic job request model"""

    job_type: str
    parameters: Dict[str, Any]
    priority: JobPriority = Field(default=JobPriority.NORMAL)
    callback_url: Optional[str] = None
    notification_email: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=3600, ge=60, le=86400)


class JobStatus(str, Enum):
    """Job status enumeration"""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class JobInfo(BaseModel):
    """Job information model"""

    job_id: str
    job_type: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress: Optional[float] = Field(None, ge=0, le=100)
    result_url: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    eta: Optional[datetime] = None
    priority: JobPriority


class JobListResponse(BaseModel):
    """Job list response model"""

    jobs: List[JobInfo]
    total: int
    limit: int
    offset: int
    filter: Optional[Dict[str, Any]] = None


# Configuration Models
class DatabaseConfig(BaseModel):
    """Database configuration model"""

    url: str
    pool_size: Optional[int] = Field(default=10, ge=1, le=50)
    timeout: Optional[int] = Field(default=30, ge=5, le=300)
    ssl_enabled: bool = Field(default=False)


class CacheConfig(BaseModel):
    """Cache configuration model"""

    enabled: bool = Field(default=True)
    ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    max_size: int = Field(default=1000, ge=10, le=10000)


class APIConfig(BaseModel):
    """API configuration model"""

    title: str = Field(default="EcoSystemiser API")
    description: str = Field(default="Sustainable Energy System Analysis Platform")
    version: str = Field(default="3.0.0")
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    cors_methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    cors_headers: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit: Optional[str] = Field(default="100/hour")


class SystemConfig(BaseModel):
    """System configuration model"""

    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    database: DatabaseConfig
    cache: CacheConfig
    api: APIConfig


# Metrics and Monitoring Models
class SystemMetrics(BaseModel):
    """System metrics model"""

    cpu_usage: float = Field(ge=0, le=100)
    memory_usage: float = Field(ge=0, le=100)
    disk_usage: float = Field(ge=0, le=100)
    active_connections: int = Field(ge=0)
    request_rate: float = Field(ge=0)
    error_rate: float = Field(ge=0, le=100)
    uptime_seconds: int = Field(ge=0)


class PerformanceMetrics(BaseModel):
    """Performance metrics model"""

    avg_response_time: float = Field(ge=0)
    p95_response_time: float = Field(ge=0)
    p99_response_time: float = Field(ge=0)
    requests_per_second: float = Field(ge=0)
    cache_hit_rate: float = Field(ge=0, le=100)


class MonitoringResponse(BaseModel):
    """Monitoring response model"""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    system_metrics: SystemMetrics
    performance_metrics: PerformanceMetrics
    health_checks: Dict[str, bool]
    alerts: Optional[List[Dict[str, Any]]] = None


# Legacy API Models
class LegacyRedirect(BaseModel):
    """Legacy API redirect response"""

    message: str
    redirect: str
    deprecated_version: str
    current_version: str
    migration_guide: Optional[str] = None


# Batch Processing Models
class BatchRequest(BaseModel):
    """Batch processing request"""

    requests: List[Dict[str, Any]] = Field(min_items=1, max_items=100)
    parallel: bool = Field(default=True)
    partial_success: bool = Field(default=True)
    batch_id: Optional[str] = None


class BatchResponse(BaseModel):
    """Batch processing response"""

    batch_id: str
    total_requests: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]
    errors: Optional[List[Dict[str, Any]]] = None
    processing_time: float


# Export Models
class ExportFormat(str, Enum):
    """Export format enumeration"""

    JSON = "json"
    CSV = "csv"
    XLSX = "xlsx"
    PARQUET = "parquet"
    NETCDF = "netcdf"
    HDF5 = "hdf5"


class ExportRequest(BaseModel):
    """Export request model"""

    data_id: str
    format: ExportFormat
    compression: bool = Field(default=False)
    include_metadata: bool = Field(default=True)
    custom_fields: Optional[List[str]] = None


class ExportResponse(BaseModel):
    """Export response model"""

    export_id: str
    download_url: str
    format: ExportFormat
    size_bytes: int
    expires_at: datetime
    checksum: Optional[str] = None
