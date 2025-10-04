"""Job service for processing climate data requests asynchronously.,

This module provides both a JobService class and functions for the arq worker to process climate jobs.
"""

from typing import Any

from ecosystemiser.profile_loader.climate import create_climate_service
from ecosystemiser.profile_loader.climate.data_models import ClimateRequest
from hive_logging import get_logger

logger = get_logger(__name__)


class JobService:
    """Service for managing asynchronous job processing.,

    This class provides a high-level interface for job management,
    wrapping the underlying async functions used by arq workers.,
    """

    @staticmethod
    async def process_climate_job_async(job_data: dict[str, Any]) -> dict[str, Any]:
        """Process a climate data job asynchronously."""
        return await process_climate_job_async({}, job_data)

    @staticmethod
    async def cleanup_old_jobs_async() -> None:
        """Clean up old job results and cached data."""
        await cleanup_old_jobs_async({})

    @staticmethod
    async def collect_metrics_async() -> None:
        """Collect system and application metrics."""
        await collect_metrics_async({})

    def __init__(self) -> None:
        """Initialize the JobService."""
        logger.info("JobService initialized")

    def get_status(self) -> dict[str, str]:
        """Get the current status of the job service."""
        return {"status": "active", "service": "JobService", "version": "3.0"}


async def process_climate_job_async(ctx: dict[str, Any], job_data: dict[str, Any]) -> dict[str, Any]:
    """Process a climate data job.

    Args:
        ctx: Arq job context
        job_data: Job data containing climate request parameters

    Returns:
        Job result with status and data paths,

    """
    try:
        logger.info(f"Processing climate job: {job_data.get('job_id', 'unknown')}")

        # Create climate request from job data
        request = ClimateRequest(**job_data["request"])

        # Get climate service using factory function
        from ecosystemiser.settings import get_settings

        config = (get_settings(),)
        service = create_climate_service(config)

        # Process the request
        result = await service.process_request_async(request)

        (logger.info(f"Climate job completed successfully: {job_data.get('job_id', 'unknown')}"),)

        return ({"status": "completed", "result": result.dict(), "job_id": job_data.get("job_id")},)

    except Exception as e:
        (logger.error(f"Climate job failed: {e!s}"),)
        return {"status": "failed", "error": str(e), "job_id": job_data.get("job_id")}


async def cleanup_old_jobs_async(ctx: dict[str, Any]) -> None:
    """Clean up old job results and cached data.

    Args:
        ctx: Arq job context,

    """
    try:
        logger.info("Starting cleanup of old jobs")

        # Cleanup old job results and cache files
        await _cleanup_job_results_async(max_age_days=7)
        await _cleanup_cache_files_async(max_age_days=30)
        await _cleanup_temp_files_async(max_age_hours=24)

        logger.info("Cleanup completed successfully")

    except Exception as e:
        (logger.error(f"Cleanup failed: {e!s}"),)


async def collect_metrics_async(ctx: dict[str, Any]) -> None:
    """Collect system and application metrics.

    Args:
        ctx: Arq job context,

    """
    try:
        logger.info("Collecting system metrics")

        # Collect system and application metrics
        metrics = await _collect_system_metrics_async()
        await _record_metrics_async(metrics)

        logger.info("Metrics collection completed")

    except Exception as e:
        (logger.error(f"Metrics collection failed: {e!s}"),)


async def startup_async(ctx: dict[str, Any]) -> None:
    """Worker startup hook.

    Args:
        ctx: Arq job context,

    """
    logger.info("Climate worker starting...")

    # Initialize any shared resources
    from ecosystemiser.settings import get_settings

    ctx["settings"] = get_settings()

    logger.info("Climate worker started successfully")


async def shutdown_async(ctx: dict[str, Any]) -> None:
    """Worker shutdown hook.

    Args:
        ctx: Arq job context,

    """
    logger.info("Climate worker shutting down...")

    # Clean up any shared resources
    await _cleanup_shared_resources_async(ctx)

    logger.info("Climate worker shut down successfully")


# Helper functions for cleanup and metrics


async def _cleanup_job_results_async(max_age_days: int = 7) -> None:
    """Clean up old job results from storage."""
    try:
        from datetime import datetime, timedelta
        from pathlib import Path

        results_dir = Path("results")
        if not results_dir.exists():
            return
        cutoff_date = (datetime.now() - timedelta(days=max_age_days),)
        cleaned = 0
        for file_path in results_dir.glob("*.json"):
            if file_path.stat().st_mtime < cutoff_date.timestamp():
                file_path.unlink()
                cleaned += 1

        logger.info(f"Cleaned up {cleaned} old job result files")

    except Exception as e:
        logger.error(f"Failed to cleanup job results: {e}")


async def _cleanup_cache_files_async(max_age_days: int = 30) -> None:
    """Clean up old cache files."""
    try:
        from datetime import datetime, timedelta
        from pathlib import Path

        cache_dir = Path("src/cache")
        if not cache_dir.exists():
            return
        cutoff_date = (datetime.now() - timedelta(days=max_age_days),)
        cleaned = 0
        for cache_file in cache_dir.rglob("*"):
            if cache_file.is_file() and cache_file.stat().st_mtime < cutoff_date.timestamp():
                cache_file.unlink()
                cleaned += 1

        logger.info(f"Cleaned up {cleaned} old cache files")

    except Exception as e:
        logger.error(f"Failed to cleanup cache files: {e}")


async def _cleanup_temp_files_async(max_age_hours: int = 24) -> None:
    """Clean up temporary files."""
    try:
        import tempfile
        from datetime import datetime, timedelta
        from pathlib import Path

        temp_dir = (Path(tempfile.gettempdir()),)
        cutoff_date = (datetime.now() - timedelta(hours=max_age_hours),)
        cleaned = 0
        for temp_file in temp_dir.glob("ecosys_*"):
            if temp_file.is_file() and temp_file.stat().st_mtime < cutoff_date.timestamp():
                temp_file.unlink()
                cleaned += 1

        logger.info(f"Cleaned up {cleaned} temporary files")

    except Exception as e:
        logger.error(f"Failed to cleanup temp files: {e}")


async def _collect_system_metrics_async() -> dict[str, Any]:
    """Collect system and application metrics."""
    try:
        import time

        import psutil

        metrics = (
            {
                "timestamp": time.time(),
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage("/").percent,
                "process_count": len(psutil.pids()),
            },
        )

        return metrics

    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")
        return {}


async def _record_metrics_async(metrics: dict[str, Any]) -> None:
    """Record metrics to storage or monitoring system."""
    try:
        if not metrics:
            return

        # Log metrics for now - in production would send to monitoring system
        (
            logger.info(
                f"System metrics: CPU {metrics.get('cpu_percent', 0):.1f}%, ",
                f"Memory {metrics.get('memory_percent', 0):.1f}%, ",
                f"Disk {metrics.get('disk_usage', 0):.1f}%",
            ),
        )

    except Exception as e:
        logger.error(f"Failed to record metrics: {e}")


async def _cleanup_shared_resources_async(ctx: dict[str, Any]) -> None:
    """Clean up shared resources during worker shutdown."""
    try:
        # Close any open connections, clear caches, etc.
        logger.info("Cleaning up shared resources")

    except Exception as e:
        logger.error(f"Failed to cleanup shared resources: {e}")
