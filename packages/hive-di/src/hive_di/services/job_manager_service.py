"""
Job Manager Service Implementation

Injectable job manager service that replaces the global job manager singleton.
Provides job scheduling and management with proper dependency injection.
"""

import json
import uuid
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from ..interfaces import (
    IJobManagerService,
    IConfigurationService,
    IDatabaseConnectionService,
    IEventBusService,
    IDisposable
)


class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Job data structure"""
    job_id: str
    job_type: str
    config: Dict[str, Any]
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    results: Optional[Dict[str, Any]]
    error_message: Optional[str]
    progress: float  # 0.0 to 1.0


class JobManagerService(IJobManagerService, IDisposable):
    """
    Injectable job manager service

    Replaces the global job manager singleton with a proper service that can be
    configured and injected independently.
    """

    def __init__(self,
                 configuration_service: IConfigurationService,
                 database_service: IDatabaseConnectionService,
                 event_bus_service: IEventBusService,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize job manager service

        Args:
            configuration_service: Configuration service for getting job manager settings
            database_service: Database service for job persistence
            event_bus_service: Event bus service for job event publishing
            config: Optional override configuration
        """
        self._config_service = configuration_service
        self._db_service = database_service
        self._event_bus = event_bus_service
        self._override_config = config or {}

        # Get job manager configuration (using climate config as base for now)
        job_config = self._config_service.get_climate_config()  # Placeholder
        self._config = {**job_config, **self._override_config}

        # Job manager settings
        self.max_concurrent_jobs = self._config.get('max_parallel_requests', 5)
        self.job_timeout = self._config.get('job_timeout', 3600)  # 1 hour default
        self.cleanup_completed_after_days = self._config.get('cleanup_completed_after_days', 7)

        # Job tracking
        self._active_jobs: Dict[str, Job] = {}
        self._job_lock = threading.RLock()
        self._running_jobs_count = 0

        # Initialize database tables
        self._ensure_job_tables()

    def _ensure_job_tables(self) -> None:
        """Ensure job storage tables exist"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()

            # Jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    config TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    results TEXT,
                    error_message TEXT,
                    progress REAL DEFAULT 0.0
                )
            """)

            # Indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status_created
                ON jobs(status, created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_type_status
                ON jobs(job_type, status)
            """)

            conn.commit()

    def _create_job_id(self) -> str:
        """Create a unique job ID"""
        return str(uuid.uuid4())

    def _save_job(self, job: Job) -> None:
        """Save job to database"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO jobs (
                    job_id, job_type, config, status, created_at,
                    started_at, completed_at, results, error_message, progress
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id,
                job.job_type,
                json.dumps(job.config),
                job.status.value,
                job.created_at.isoformat(),
                job.started_at.isoformat() if job.started_at else None,
                job.completed_at.isoformat() if job.completed_at else None,
                json.dumps(job.results) if job.results else None,
                job.error_message,
                job.progress
            ))
            conn.commit()

    def _load_job(self, job_id: str) -> Optional[Job]:
        """Load job from database"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()

        if not row:
            return None

        row_dict = dict(row)
        return Job(
            job_id=row_dict['job_id'],
            job_type=row_dict['job_type'],
            config=json.loads(row_dict['config']),
            status=JobStatus(row_dict['status']),
            created_at=datetime.fromisoformat(row_dict['created_at']),
            started_at=datetime.fromisoformat(row_dict['started_at']) if row_dict['started_at'] else None,
            completed_at=datetime.fromisoformat(row_dict['completed_at']) if row_dict['completed_at'] else None,
            results=json.loads(row_dict['results']) if row_dict['results'] else None,
            error_message=row_dict['error_message'],
            progress=row_dict['progress']
        )

    def _publish_job_event(self, job: Job, event_type: str) -> None:
        """Publish job event to event bus"""
        try:
            self._event_bus.publish(
                event_type=f"job.{event_type}",
                payload={
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "status": job.status.value,
                    "progress": job.progress,
                    "created_at": job.created_at.isoformat()
                },
                source_agent="job_manager_service",
                correlation_id=job.job_id
            )
        except Exception:
            # Don't let event publishing errors break job management
            pass

    def _execute_job(self, job: Job) -> None:
        """Execute a job (placeholder implementation)"""
        try:
            with self._job_lock:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now(timezone.utc)
                job.progress = 0.0
                self._save_job(job)
                self._publish_job_event(job, "started")

            # Simulate job execution
            import time
            total_steps = 10
            for step in range(total_steps):
                time.sleep(0.1)  # Simulate work
                job.progress = (step + 1) / total_steps

                with self._job_lock:
                    self._save_job(job)

            # Job completed successfully
            job.results = {
                "message": f"Job {job.job_type} completed successfully",
                "processed_items": 100,
                "execution_time": 1.0
            }
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 1.0

        except Exception as e:
            # Job failed
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = str(e)

        finally:
            with self._job_lock:
                self._save_job(job)
                self._publish_job_event(job, job.status.value)
                if job.job_id in self._active_jobs:
                    del self._active_jobs[job.job_id]
                self._running_jobs_count = max(0, self._running_jobs_count - 1)

    # IJobManagerService interface implementation

    def submit_job(self, job_config: Dict[str, Any]) -> str:
        """Submit a job and return job ID"""
        job_id = self._create_job_id()
        job_type = job_config.get('type', 'unknown')

        # Check if we can accept more jobs
        with self._job_lock:
            if self._running_jobs_count >= self.max_concurrent_jobs:
                raise RuntimeError(f"Maximum concurrent jobs ({self.max_concurrent_jobs}) reached")

            job = Job(
                job_id=job_id,
                job_type=job_type,
                config=job_config,
                status=JobStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                started_at=None,
                completed_at=None,
                results=None,
                error_message=None,
                progress=0.0
            )

            # Save to database
            self._save_job(job)

            # Add to active jobs
            self._active_jobs[job_id] = job
            self._running_jobs_count += 1

            # Publish job created event
            self._publish_job_event(job, "created")

        # Start job execution in background thread
        import threading
        job_thread = threading.Thread(
            target=self._execute_job,
            args=(job,),
            daemon=True
        )
        job_thread.start()

        return job_id

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a specific job"""
        # Check active jobs first
        with self._job_lock:
            if job_id in self._active_jobs:
                job = self._active_jobs[job_id]
            else:
                # Load from database
                job = self._load_job(job_id)

        if not job:
            raise ValueError(f"Job {job_id} not found")

        return {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status.value,
            "progress": job.progress,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
            "has_results": job.results is not None
        }

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        with self._job_lock:
            if job_id in self._active_jobs:
                job = self._active_jobs[job_id]
                if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
                    job.status = JobStatus.CANCELLED
                    job.completed_at = datetime.now(timezone.utc)
                    self._save_job(job)
                    self._publish_job_event(job, "cancelled")
                    return True
            else:
                # Try to load and cancel from database
                job = self._load_job(job_id)
                if job and job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
                    job.status = JobStatus.CANCELLED
                    job.completed_at = datetime.now(timezone.utc)
                    self._save_job(job)
                    self._publish_job_event(job, "cancelled")
                    return True

        return False

    def get_job_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get results from a completed job"""
        # Check active jobs first
        with self._job_lock:
            if job_id in self._active_jobs:
                job = self._active_jobs[job_id]
            else:
                # Load from database
                job = self._load_job(job_id)

        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status != JobStatus.COMPLETED:
            return None

        return job.results

    # IDisposable interface implementation

    def dispose(self) -> None:
        """Clean up job manager service resources"""
        with self._job_lock:
            # Cancel all active jobs
            for job in self._active_jobs.values():
                if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
                    job.status = JobStatus.CANCELLED
                    job.completed_at = datetime.now(timezone.utc)
                    self._save_job(job)

            self._active_jobs.clear()
            self._running_jobs_count = 0

    # Additional utility methods

    def get_active_job_count(self) -> int:
        """Get number of active jobs"""
        with self._job_lock:
            return len(self._active_jobs)

    def get_job_statistics(self) -> Dict[str, Any]:
        """Get job manager statistics"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()

            # Total jobs by status
            cursor.execute("""
                SELECT status, COUNT(*) FROM jobs GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())

            # Jobs by type
            cursor.execute("""
                SELECT job_type, COUNT(*) FROM jobs GROUP BY job_type
            """)
            type_counts = dict(cursor.fetchall())

            # Recent jobs (last 24 hours)
            from datetime import timedelta
            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            cursor.execute("""
                SELECT COUNT(*) FROM jobs WHERE created_at >= ?
            """, (yesterday,))
            recent_jobs = cursor.fetchone()[0]

        return {
            "active_jobs": self.get_active_job_count(),
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "by_status": status_counts,
            "by_type": type_counts,
            "recent_jobs_24h": recent_jobs
        }

    def cleanup_old_jobs(self) -> int:
        """Clean up old completed jobs"""
        from datetime import timedelta

        cutoff_date = (
            datetime.now(timezone.utc) -
            timedelta(days=self.cleanup_completed_after_days)
        ).isoformat()

        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM jobs
                WHERE status IN ('completed', 'failed', 'cancelled')
                AND completed_at < ?
            """, (cutoff_date,))
            deleted_count = cursor.rowcount
            conn.commit()

        return deleted_count

    def get_jobs_by_status(self, status: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get jobs by status"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM jobs WHERE status = ?
                ORDER BY created_at DESC LIMIT ?
            """, (status, limit))
            rows = cursor.fetchall()

        jobs = []
        for row in rows:
            job_dict = dict(row)
            job_dict['config'] = json.loads(job_dict['config'])
            if job_dict['results']:
                job_dict['results'] = json.loads(job_dict['results'])
            jobs.append(job_dict)

        return jobs