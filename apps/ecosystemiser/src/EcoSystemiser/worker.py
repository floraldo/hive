"""
Arq worker configuration for processing climate jobs.

Run with: arq ecosystemiser.worker.WorkerSettings
"""

from ecosystemiser.hive_logging_adapter import get_logger
from typing import Any, Dict

from arq import cron
from arq.connections import RedisSettings

from ecosystemiser.settings import get_settings
from ecosystemiser.services.job_service import process_climate_job, cleanup_old_jobs, collect_metrics, startup, shutdown

logger = get_logger(__name__)

# Get settings
settings = get_settings()

class WorkerSettings:
    """Arq worker settings"""
    
    # Redis connection
    redis_settings = RedisSettings(
        host=settings.queue.redis_url.split('://')[1].split(':')[0],
        port=int(settings.queue.redis_url.split(':')[-1].split('/')[0]),
        database=0
    )
    
    # Queue configuration
    queue_name = "default"
    max_jobs = settings.queue.worker_concurrency
    job_timeout = settings.queue.job_timeout
    keep_result = settings.queue.result_ttl
    retry_jobs = True
    max_tries = settings.queue.max_retries
    
    # Health check
    health_check_interval = settings.queue.worker_heartbeat
    
    # Functions to run
    functions = [
        process_climate_job,
    ]
    
    # Cron jobs
    cron_jobs = [
        cron(cleanup_old_jobs, hour=3, minute=0),  # Clean up at 3 AM daily
        cron(collect_metrics, minute={0, 15, 30, 45}),  # Collect metrics every 15 min
    ]
    
    # Startup/shutdown hooks
    on_startup = startup
    on_shutdown = shutdown

