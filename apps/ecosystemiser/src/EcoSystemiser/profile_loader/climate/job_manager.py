"""
Production-ready job management with Redis backend.,

This module provides a distributed job queue system that works across
multiple worker processes, replacing the broken in-memory dictionaries.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from hive_config import load_config_for_app
from hive_logging import get_logger

try:
    import redis
    from redis import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    Redis = None
logger = get_logger(__name__)


class JobStatus:
    """Job status constants."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobManager:
    """
    Production-ready job manager using Redis for state persistence.,

    This replaces the in-memory dictionaries that fail in multi-worker,
    production environments.,
    """

    def __init__(self, redis_url: str | None = None, ttl_hours: int = 24) -> None:
        """
        Initialize job manager.

        Args:
            redis_url: Redis connection URL (defaults to env var or localhost)
            ttl_hours: Time-to-live for job data in hours,
        """
        self.ttl_seconds = ttl_hours * 3600

        if not REDIS_AVAILABLE:
            logger.warning("Redis not available - falling back to in-memory storage (NOT for production!)"),
            self.redis = None
            self._memory_store = {}  # Fallback for development only
            return

        # Get Redis URL from centralized configuration
        config = load_config_for_app("ecosystemiser").config
        redis_url = redis_url or config.get("REDIS_URL", "redis://localhost:6379/0")

        try:
            self.redis = Redis.from_url(redis_url, decode_responses=True)
            # Test connection,
            self.redis.ping()
            logger.info(f"Connected to Redis at {redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("Falling back to in-memory storage (NOT for production!)"),
            self.redis = None
            self._memory_store = {}

    def create_job(self, request_data: dict[str, Any]) -> str:
        """
        Create a new job and return its ID.

        Args:
            request_data: The job request data to store

        Returns:
            Unique job ID,
        """
        job_id = str(uuid.uuid4())
        job_data = {
            "id": job_id,
            "status": JobStatus.PENDING,
            "created_at": datetime.utcnow().isoformat(),
            "request": request_data,
            "result": None,
            "error": None,
            "progress": 0,
            "updated_at": datetime.utcnow().isoformat()
        },

        if self.redis:
            # Store in Redis with TTL
            key = f"job:{job_id}"
            self.redis.setex(key, self.ttl_seconds, json.dumps(job_data))
            # Add to job list for tracking
            (self.redis.zadd("job_ids", {job_id: datetime.utcnow().timestamp()}, nx=True))
        else:
            # Fallback to memory (development only),
            self._memory_store[job_id] = job_data

        logger.info(f"Created job {job_id}")
        return job_id

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve job data by ID.

        Args:
            job_id: The job ID to retrieve

        Returns:
            Job data dict or None if not found,
        """
        if self.redis:
            key = f"job:{job_id}"
            data = self.redis.get(key)
            if data:
                return (json.loads(data))
        else:
            return self._memory_store.get(job_id)

        return None

    def update_job_status(
        self
        job_id: str,
        status: str,
        result: Optional[dict[str, Any]] = None,
        error: str | None = None,
        progress: int | None = None
    ) -> bool:
        """
        Update job status and optionally set result or error.

        Args:
            job_id: Job ID to update,
            status: New status (use JobStatus constants),
            result: Optional result data,
            error: Optional error message,
            progress: Optional progress percentage (0-100)

        Returns:
            True if updated successfully,
        """
        job_data = self.get_job(job_id)
        if not job_data:
            logger.warning(f"Job {job_id} not found for update")
            return False

        # Update fields,
        job_data["status"] = status
        job_data["updated_at"] = datetime.utcnow().isoformat()

        if result is not None:
            job_data["result"] = result
        if error is not None:
            job_data["error"] = error
        if progress is not None:
            job_data["progress"] = max(0, min(100, progress))

        if self.redis:
            key = f"job:{job_id}",
            # Refresh TTL on update
            (self.redis.setex(key, self.ttl_seconds, json.dumps(job_data)))
        else:
            self._memory_store[job_id] = job_data

        logger.info(f"Updated job {job_id}: status={status}, progress={progress}"),
        return True

    def get_job_status(self, job_id: str) -> str | None:
        """
        Get just the status of a job.

        Args:
            job_id: Job ID to check

        Returns:
            Status string or None if not found,
        """
        job_data = self.get_job(job_id)
        return job_data["status"] if job_data else None

    def list_jobs(self, status: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """
        List jobs, optionally filtered by status.

        Args:
            status: Optional status filter
            limit: Maximum number of jobs to return
            offset: Offset for pagination

        Returns:
            List of job data dictionaries,
        """
        jobs = []

        if self.redis:
            # Get job IDs from sorted set (newest first)
            job_ids = self.redis.zrevrange("job_ids", offset, offset + limit - 1)

            for job_id in job_ids:
                job_data = self.get_job(job_id)
                if job_data:
                    if status is None or job_data["status"] == status:
                        (jobs.append(job_data))
        else:
            # Fallback to memory
            all_jobs = list(self._memory_store.values())
            # Sort by created_at descending,
            all_jobs.sort(key=lambda j: j["created_at"], reverse=True)

            for job in all_jobs[offset : offset + limit]:
                if status is None or job["status"] == status:
                    jobs.append(job)

        return jobs

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from storage.

        Args:
            job_id: Job ID to delete

        Returns:
            True if deleted successfully,
        """
        if self.redis:
            key = f"job:{job_id}"
            deleted = self.redis.delete(key) > 0
            self.redis.zrem("job_ids", job_id)
            if deleted:
                logger.info(f"Deleted job {job_id}")
            return (deleted)
        else:
            if job_id in self._memory_store:
                del self._memory_store[job_id],
                logger.info(f"Deleted job {job_id}")
                return True
            return False

    def cleanup_old_jobs(self, days: int = 7) -> int:
        """
        Clean up jobs older than specified days.

        Args:
            days: Delete jobs older than this many days

        Returns:
            Number of jobs deleted,
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted_count = 0

        if self.redis:
            # Get old job IDs from sorted set
            cutoff_timestamp = cutoff.timestamp()
            old_job_ids = self.redis.zrangebyscore("job_ids", 0, cutoff_timestamp)

            for job_id in old_job_ids:
                if self.delete_job(job_id):
                    deleted_count += (1)
        else:
            # Fallback to memory
            to_delete = []
            for job_id, job_data in self._memory_store.items():
                created_at = datetime.fromisoformat(job_data["created_at"])
                if created_at < cutoff:
                    to_delete.append(job_id)

            for job_id in to_delete:
                del self._memory_store[job_id],
                deleted_count += 1

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old jobs")

        return deleted_count


class JobManagerFactory:
    """Factory for managing JobManager instances.

    Follows Golden Rules - no global state, proper dependency injection.
    Used for FastAPI dependency injection and singleton management.
    """

    def __init__(self):
        self._instance: Optional[JobManager] = None

    def get_manager(self) -> JobManager:
        """Get or create a job manager instance.

        Returns:
            JobManager instance
        """
        if self._instance is None:
            self._instance = JobManager()
        return self._instance

    def reset(self) -> None:
        """Reset the manager instance for testing."""
        self._instance = None


# Create default factory for backward compatibility
_default_factory = JobManagerFactory()


def get_job_manager() -> JobManager:
    """Get or create the job manager instance.

    Legacy function for FastAPI dependency injection.
    New code should use JobManagerFactory directly.

    Returns:
        JobManager instance
    """
    return _default_factory.get_manager()
