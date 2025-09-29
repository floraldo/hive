#!/usr/bin/env python3
"""
Pipeline Monitor for AI Planner -> Queen -> Worker Integration

Provides comprehensive monitoring, logging, and reporting for the complete
autonomous task execution pipeline to ensure reliable operation.
"""

import asyncio
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from hive_logging import get_logger

from ..db.database import get_connection
from ..db.planning_integration import planning_integration

logger = get_logger(__name__)


class PipelineStage(Enum):
    """Stages in the AI Planner -> Queen -> Worker pipeline"""

    PLANNING_QUEUE = "planning_queue"
    AI_PLANNER = "ai_planner"
    EXECUTION_PLAN = "execution_plan"
    QUEEN_PICKUP = "queen_pickup"
    WORKER_EXECUTION = "worker_execution"
    COMPLETION = "completion"


class HealthStatus(Enum):
    """Health status indicators"""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class PipelineMetrics:
    """Metrics for pipeline monitoring"""

    # Planning Queue Metrics
    pending_planning_tasks: int = 0
    assigned_planning_tasks: int = 0
    completed_planning_tasks: int = 0
    failed_planning_tasks: int = 0

    # Execution Plan Metrics
    generated_plans: int = 0
    executing_plans: int = 0
    completed_plans: int = 0
    failed_plans: int = 0

    # Task Execution Metrics
    queued_subtasks: int = 0
    assigned_subtasks: int = 0
    in_progress_subtasks: int = 0
    completed_subtasks: int = 0
    failed_subtasks: int = 0

    # Performance Metrics
    avg_planning_time_minutes: float = 0.0
    avg_execution_time_minutes: float = 0.0
    avg_plan_completion_percentage: float = 0.0

    # Health Indicators
    stuck_tasks_count: int = 0
    error_rate_percentage: float = 0.0
    pipeline_throughput_per_hour: float = 0.0

    # Timestamps
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary"""
        return asdict(self)


@dataclass
class PipelineAlert:
    """Alert for pipeline issues"""

    severity: HealthStatus
    stage: PipelineStage
    message: str
    details: dict[str, Any]
    timestamp: str
    alert_id: str


class PipelineMonitor:
    """Comprehensive monitor for the AI Planner -> Queen -> Worker pipeline"""

    def __init__(self, alert_thresholds: dict[str, Any] | None = None) -> None:
        """
        Initialize pipeline monitor

        Args:
            alert_thresholds: Custom thresholds for alerts
        """
        self.alert_thresholds = alert_thresholds or {
            "stuck_task_minutes": 30,
            "error_rate_percentage": 10.0,
            "low_throughput_per_hour": 1.0,
            "plan_completion_warning": 80.0,
            "queue_backup_count": 20,
        }

        self.alerts: list[PipelineAlert] = []
        self.metrics_history: list[PipelineMetrics] = []
        self.last_check_time = datetime.now(UTC)

        logger.info("Pipeline monitor initialized")

    def collect_metrics(self) -> PipelineMetrics:
        """Collect comprehensive pipeline metrics"""
        try:
            with get_connection() as conn:
                metrics = PipelineMetrics()

                # Planning Queue Metrics
                cursor = conn.execute(
                    """,
                    SELECT status, COUNT(*) FROM planning_queue GROUP BY status,
                """
                )
                for status, count in cursor.fetchall():
                    if status == "pending":
                        metrics.pending_planning_tasks = count
                    elif status == "assigned":
                        metrics.assigned_planning_tasks = count
                    elif status == "planned":
                        metrics.completed_planning_tasks = count
                    elif status == "failed":
                        metrics.failed_planning_tasks = count

                # Execution Plan Metrics
                cursor = conn.execute(
                    """,
                    SELECT status, COUNT(*) FROM execution_plans GROUP BY status,
                """
                )
                for status, count in cursor.fetchall():
                    if status == "generated":
                        metrics.generated_plans = count
                    elif status == "executing":
                        metrics.executing_plans = count
                    elif status == "completed":
                        metrics.completed_plans = count
                    elif status == "failed":
                        metrics.failed_plans = count

                # Subtask Metrics
                cursor = conn.execute(
                    """,
                    SELECT status, COUNT(*) FROM tasks,
                    WHERE task_type = 'planned_subtask',
                    GROUP BY status,
                """
                )
                for status, count in cursor.fetchall():
                    if status == "queued":
                        metrics.queued_subtasks = count
                    elif status == "assigned":
                        metrics.assigned_subtasks = count
                    elif status == "in_progress":
                        metrics.in_progress_subtasks = count
                    elif status == "completed":
                        metrics.completed_subtasks = count
                    elif status == "failed":
                        metrics.failed_subtasks = count

                # Performance Metrics
                metrics.avg_planning_time_minutes = self._calculate_avg_planning_time(conn)
                metrics.avg_execution_time_minutes = self._calculate_avg_execution_time(conn)
                metrics.avg_plan_completion_percentage = self._calculate_avg_plan_completion(conn)

                # Health Indicators
                metrics.stuck_tasks_count = self._count_stuck_tasks(conn)
                metrics.error_rate_percentage = self._calculate_error_rate(conn)
                metrics.pipeline_throughput_per_hour = self._calculate_throughput(conn)

                metrics.last_updated = datetime.now(UTC).isoformat()

                return metrics

        except Exception as e:
            logger.error(f"Error collecting pipeline metrics: {e}")
            return PipelineMetrics(last_updated=datetime.now(UTC).isoformat())

    def _calculate_avg_planning_time(self, conn) -> float:
        """Calculate average time from planning queue to execution plan"""
        cursor = conn.execute(
            """,
            SELECT AVG(
                (julianday(ep.generated_at) - julianday(pq.created_at)) * 24 * 60
            ) as avg_minutes,
            FROM execution_plans ep,
            JOIN planning_queue pq ON ep.planning_task_id = pq.id
            WHERE ep.generated_at IS NOT NULL
            AND pq.created_at > datetime('now', '-24 hours')
        """
        )
        result = cursor.fetchone()
        return round(result[0] if result and result[0] else 0.0, 2)

    def _calculate_avg_execution_time(self, conn) -> float:
        """Calculate average execution time for subtasks"""
        cursor = conn.execute(
            """,
            SELECT AVG(
                (julianday(completed_at) - julianday(started_at)) * 24 * 60
            ) as avg_minutes,
            FROM tasks,
            WHERE task_type = 'planned_subtask'
            AND status = 'completed'
            AND started_at IS NOT NULL
            AND completed_at IS NOT NULL
            AND started_at > datetime('now', '-24 hours')
        """
        )
        result = cursor.fetchone()
        return round(result[0] if result and result[0] else 0.0, 2)

    def _calculate_avg_plan_completion(self, conn) -> float:
        """Calculate average completion percentage for active plans"""
        cursor = conn.execute(
            """,
            SELECT ep.id FROM execution_plans ep,
            WHERE ep.status IN ('executing', 'completed')
        """
        )

        plan_ids = [row[0] for row in cursor.fetchall()]
        if not plan_ids:
            return 0.0

        total_completion = 0.0
        for plan_id in plan_ids:
            completion_status = planning_integration.get_plan_completion_status(plan_id)
            total_completion += completion_status.get("completion_percentage", 0.0)

        return round(total_completion / len(plan_ids), 2)

    def _count_stuck_tasks(self, conn) -> int:
        """Count tasks that appear to be stuck"""
        stuck_threshold_minutes = self.alert_thresholds["stuck_task_minutes"]
        cursor = conn.execute(
            """,
            SELECT COUNT(*) FROM tasks,
            WHERE status IN ('assigned', 'in_progress')
            AND started_at IS NOT NULL,
            AND (julianday('now') - julianday(started_at)) * 24 * 60 > ?
        """,
            (stuck_threshold_minutes,),
        )
        return cursor.fetchone()[0]

    def _calculate_error_rate(self, conn) -> float:
        """Calculate error rate percentage over last 24 hours"""
        cursor = conn.execute(
            """,
            SELECT,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                COUNT(*) as total_count,
            FROM tasks,
            WHERE task_type = 'planned_subtask'
            AND created_at > datetime('now', '-24 hours')
        """
        )
        result = cursor.fetchone()
        failed_count, total_count = result

        if total_count == 0:
            return 0.0

        return round((failed_count / total_count) * 100, 2)

    def _calculate_throughput(self, conn) -> float:
        """Calculate pipeline throughput (completed tasks per hour)"""
        cursor = conn.execute(
            """,
            SELECT COUNT(*) FROM tasks,
            WHERE task_type = 'planned_subtask',
            AND status = 'completed',
            AND completed_at > datetime('now', '-1 hour')
        """
        )
        return float(cursor.fetchone()[0])

    def check_health(self, metrics: PipelineMetrics) -> tuple[HealthStatus, list[PipelineAlert]]:
        """
        Check pipeline health and generate alerts

        Args:
            metrics: Current pipeline metrics

        Returns:
            Overall health status and list of alerts
        """
        alerts = []
        health_scores = []

        # Check for stuck tasks
        if metrics.stuck_tasks_count > 0:
            severity = HealthStatus.CRITICAL if metrics.stuck_tasks_count > 5 else HealthStatus.WARNING
            alerts.append(
                PipelineAlert(
                    severity=severity,
                    stage=PipelineStage.WORKER_EXECUTION,
                    message=f"{metrics.stuck_tasks_count} tasks appear to be stuck",
                    details={
                        "stuck_count": metrics.stuck_tasks_count,
                        "threshold_minutes": self.alert_thresholds["stuck_task_minutes"],
                    },
                    timestamp=datetime.now(UTC).isoformat(),
                    alert_id=f"stuck_tasks_{int(time.time())}",
                )
            )
            health_scores.append(0 if severity == HealthStatus.CRITICAL else 0.5)
        else:
            health_scores.append(1.0)

        # Check error rate
        if metrics.error_rate_percentage > self.alert_thresholds["error_rate_percentage"]:
            severity = HealthStatus.CRITICAL if metrics.error_rate_percentage > 25 else HealthStatus.WARNING
            alerts.append(
                PipelineAlert(
                    severity=severity,
                    stage=PipelineStage.WORKER_EXECUTION,
                    message=f"High error rate: {metrics.error_rate_percentage}%",
                    details={
                        "error_rate": metrics.error_rate_percentage,
                        "threshold": self.alert_thresholds["error_rate_percentage"],
                    },
                    timestamp=datetime.now(UTC).isoformat(),
                    alert_id=f"error_rate_{int(time.time())}",
                )
            )
            health_scores.append(0 if severity == HealthStatus.CRITICAL else 0.5)
        else:
            health_scores.append(1.0)

        # Check throughput
        if metrics.pipeline_throughput_per_hour < self.alert_thresholds["low_throughput_per_hour"]:
            alerts.append(
                PipelineAlert(
                    severity=HealthStatus.WARNING,
                    stage=PipelineStage.COMPLETION,
                    message=f"Low throughput: {metrics.pipeline_throughput_per_hour} tasks/hour",
                    details={
                        "throughput": metrics.pipeline_throughput_per_hour,
                        "threshold": self.alert_thresholds["low_throughput_per_hour"],
                    },
                    timestamp=datetime.now(UTC).isoformat(),
                    alert_id=f"throughput_{int(time.time())}",
                )
            )
            health_scores.append(0.5)
        else:
            health_scores.append(1.0)

        # Check queue backup
        total_pending = metrics.pending_planning_tasks + metrics.queued_subtasks
        if total_pending > self.alert_thresholds["queue_backup_count"]:
            alerts.append(
                PipelineAlert(
                    severity=HealthStatus.WARNING,
                    stage=PipelineStage.PLANNING_QUEUE,
                    message=f"Queue backup: {total_pending} pending tasks",
                    details={
                        "pending_count": total_pending,
                        "threshold": self.alert_thresholds["queue_backup_count"],
                    },
                    timestamp=datetime.now(UTC).isoformat(),
                    alert_id=f"queue_backup_{int(time.time())}",
                )
            )
            health_scores.append(0.5)
        else:
            health_scores.append(1.0)

        # Calculate overall health
        if not health_scores:
            overall_health = HealthStatus.UNKNOWN
        elif all(score == 1.0 for score in health_scores):
            overall_health = HealthStatus.HEALTHY
        elif any(score == 0 for score in health_scores):
            overall_health = HealthStatus.CRITICAL
        else:
            overall_health = HealthStatus.WARNING

        return overall_health, alerts

    def generate_report(
        self,
        metrics: PipelineMetrics,
        health: HealthStatus,
        alerts: list[PipelineAlert],
    ) -> str:
        """Generate human-readable pipeline status report"""
        report_lines = [
            "=" * 70,
            "AI PLANNER -> QUEEN -> WORKER PIPELINE STATUS REPORT",
            "=" * 70,
            f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Overall Health: {health.value.upper()}",
            "",
        ]

        # Health Summary
        if health == HealthStatus.HEALTHY:
            report_lines.append("🟢 SYSTEM HEALTHY - All components operating normally")
        elif health == HealthStatus.WARNING:
            report_lines.append("🟡 SYSTEM WARNING - Minor issues detected")
        elif health == HealthStatus.CRITICAL:
            report_lines.append("🔴 SYSTEM CRITICAL - Immediate attention required")
        else:
            report_lines.append("⚪ SYSTEM STATUS UNKNOWN")

        report_lines.append("")

        # Pipeline Flow Summary
        report_lines.extend(
            [
                "📊 PIPELINE FLOW SUMMARY",
                "-" * 30,
                "Planning Queue -> AI Planner:",
                f"  📝 Pending: {metrics.pending_planning_tasks}",
                f"  🤖 Processing: {metrics.assigned_planning_tasks}",
                f"  OK Completed: {metrics.completed_planning_tasks}",
                f"  FAIL Failed: {metrics.failed_planning_tasks}",
                "",
                "Execution Plans:",
                f"  📋 Generated: {metrics.generated_plans}",
                f"  🔄 Executing: {metrics.executing_plans}",
                f"  OK Completed: {metrics.completed_plans}",
                f"  FAIL Failed: {metrics.failed_plans}",
                "",
                "Subtask Execution:",
                f"  📥 Queued: {metrics.queued_subtasks}",
                f"  👤 Assigned: {metrics.assigned_subtasks}",
                f"  ⚙️ In Progress: {metrics.in_progress_subtasks}",
                f"  OK Completed: {metrics.completed_subtasks}",
                f"  FAIL Failed: {metrics.failed_subtasks}",
                "",
            ]
        )

        # Performance Metrics
        report_lines.extend(
            [
                "⚡ PERFORMANCE METRICS",
                "-" * 25,
                f"Average Planning Time: {metrics.avg_planning_time_minutes:.1f} minutes",
                f"Average Execution Time: {metrics.avg_execution_time_minutes:.1f} minutes",
                f"Plan Completion Rate: {metrics.avg_plan_completion_percentage:.1f}%",
                f"Pipeline Throughput: {metrics.pipeline_throughput_per_hour:.1f} tasks/hour",
                f"Error Rate: {metrics.error_rate_percentage:.1f}%",
                "",
            ]
        )

        # Alerts
        if alerts:
            report_lines.extend(["🚨 ACTIVE ALERTS", "-" * 15])
            for alert in alerts:
                icon = "🔴" if alert.severity == HealthStatus.CRITICAL else "🟡"
                report_lines.append(f"{icon} [{alert.stage.value.upper()}] {alert.message}")
            report_lines.append("")
        else:
            report_lines.extend(["OK NO ACTIVE ALERTS", ""])

        # Recommendations
        recommendations = self._generate_recommendations(metrics, health, alerts)
        if recommendations:
            report_lines.extend(["💡 RECOMMENDATIONS", "-" * 18])
            for i, rec in enumerate(recommendations, 1):
                report_lines.append(f"{i}. {rec}")
            report_lines.append("")

        report_lines.append("=" * 70)

        return "\n".join(report_lines)

    def _generate_recommendations(
        self,
        metrics: PipelineMetrics,
        health: HealthStatus,
        alerts: list[PipelineAlert],
    ) -> list[str]:
        """Generate actionable recommendations based on current state"""
        recommendations = []

        # High error rate recommendations
        if metrics.error_rate_percentage > 5:
            recommendations.append(f"Investigate failed tasks - error rate is {metrics.error_rate_percentage:.1f}%")

        # Low throughput recommendations
        if metrics.pipeline_throughput_per_hour < 2:
            recommendations.append("Consider increasing worker capacity or optimizing task execution")

        # Stuck tasks recommendations
        if metrics.stuck_tasks_count > 0:
            recommendations.append(f"Review {metrics.stuck_tasks_count} stuck tasks for timeout issues")

        # Queue backup recommendations
        total_pending = metrics.pending_planning_tasks + metrics.queued_subtasks
        if total_pending > 10:
            recommendations.append("Consider scaling AI Planner or Queen capacity to reduce queue backup")

        # Plan completion recommendations
        if metrics.avg_plan_completion_percentage < 80:
            recommendations.append("Review incomplete execution plans for blocking dependencies")

        # General health recommendations
        if health == HealthStatus.CRITICAL:
            recommendations.append("Immediate investigation required - multiple critical issues detected")
        elif health == HealthStatus.WARNING:
            recommendations.append("Monitor system closely and address warnings before they become critical")

        return recommendations

    def monitor_loop(self, interval_seconds: int = 60) -> None:
        """Run continuous monitoring loop"""
        logger.info(f"Starting pipeline monitor loop (interval: {interval_seconds}s)")

        while True:
            try:
                # Collect metrics
                metrics = self.collect_metrics()
                self.metrics_history.append(metrics)

                # Keep only last 24 hours of metrics
                cutoff_time = datetime.now(UTC) - timedelta(hours=24)
                self.metrics_history = [
                    m for m in self.metrics_history if datetime.fromisoformat(m.last_updated) > cutoff_time
                ]

                # Check health
                health, alerts = self.check_health(metrics)

                # Update alerts
                self.alerts = alerts

                # Log critical alerts
                for alert in alerts:
                    if alert.severity == HealthStatus.CRITICAL:
                        logger.error(f"CRITICAL ALERT: {alert.message}")
                    elif alert.severity == HealthStatus.WARNING:
                        logger.warning(f"WARNING: {alert.message}")

                # Generate and log report periodically
                if len(self.metrics_history) % 10 == 0:  # Every 10 cycles
                    report = self.generate_report(metrics, health, alerts)
                    logger.info(f"Pipeline Status Report:\n{report}")

                await asyncio.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("Pipeline monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(interval_seconds)

    async def monitor_loop_async(self, interval_seconds: int = 60) -> None:
        """Async version of monitoring loop for non-blocking operation"""
        logger.info(f"Starting async pipeline monitor loop (interval: {interval_seconds}s)")

        while True:
            try:
                # Run monitoring in thread pool to avoid blocking
                metrics = await asyncio.get_event_loop().run_in_executor(None, self.collect_metrics)

                health, alerts = await asyncio.get_event_loop().run_in_executor(None, self.check_health, metrics)

                # Update state
                self.metrics_history.append(metrics)
                self.alerts = alerts

                # Log critical alerts
                for alert in alerts:
                    if alert.severity == HealthStatus.CRITICAL:
                        logger.error(f"CRITICAL ALERT: {alert.message}")

                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                logger.info("Async pipeline monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in async monitor loop: {e}")
                await asyncio.sleep(interval_seconds)


# Global monitor instance
pipeline_monitor = PipelineMonitor()


def get_pipeline_status() -> dict[str, Any]:
    """Get current pipeline status (convenience function)"""
    metrics = pipeline_monitor.collect_metrics()
    health, alerts = pipeline_monitor.check_health(metrics)

    return {
        "health": health.value,
        "metrics": metrics.to_dict(),
        "alerts": [asdict(alert) for alert in alerts],
        "last_updated": datetime.now(UTC).isoformat(),
    }


if __name__ == "__main__":
    # Run standalone monitoring
    monitor = PipelineMonitor()
    monitor.monitor_loop(interval_seconds=30)
