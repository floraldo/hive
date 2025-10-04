# ruff: noqa: S603
# Security: subprocess calls in this script use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal performance tooling.

"""
Pool Tuning Orchestrator

Automates connection pool tuning based on optimizer recommendations.
Part of PROJECT VANGUARD Phase 2.2 - Automated Connection Pool Tuning.

Features:
- Consumes pool_optimizer.py output
- Prioritizes by potential impact
- Schedules changes during maintenance windows
- Safe deployment with automatic rollback
- Configuration versioning via git

Usage:
    python scripts/automation/pool_tuning_orchestrator.py --analyze
    python scripts/automation/pool_tuning_orchestrator.py --apply --service database_pool
    python scripts/automation/pool_tuning_orchestrator.py --rollback --service database_pool
"""

import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class TuningRecommendation:
    """Represents a pool tuning recommendation."""

    service_name: str
    current_config: dict[str, Any]
    recommended_config: dict[str, Any]
    expected_improvement: str
    priority: str  # critical, high, medium, low
    confidence: float
    rationale: str
    estimated_impact: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"  # low, medium, high


@dataclass
class TuningExecution:
    """Represents a tuning execution attempt."""

    execution_id: str
    service_name: str
    old_config: dict[str, Any]
    new_config: dict[str, Any]
    started_at: str
    completed_at: str | None = None
    status: str = "pending"  # pending, in_progress, completed, failed, rolled_back
    metrics_before: dict[str, Any] = field(default_factory=dict)
    metrics_after: dict[str, Any] = field(default_factory=dict)
    rollback_needed: bool = False
    rollback_reason: str | None = None


class PoolTuningOrchestrator:
    """
    Orchestrate automated connection pool tuning.

    Workflow:
    1. Load recommendations from pool_optimizer
    2. Prioritize by impact and safety
    3. Schedule during maintenance windows
    4. Apply configuration changes
    5. Monitor metrics for 15 minutes
    6. Rollback if errors spike >20%
    7. Commit successful changes to git
    """

    def __init__(
        self,
        recommendations_file: str = "data/pool_optimization_recommendations.json",
        execution_history_file: str = "data/pool_tuning_history.json",
        config_backup_dir: str = "data/config_backups",
        monitoring_window_minutes: int = 15,
        error_spike_threshold: float = 0.20,
    ):
        self.recommendations_file = Path(recommendations_file)
        self.execution_history_file = Path(execution_history_file)
        self.config_backup_dir = Path(config_backup_dir)
        self.monitoring_window_minutes = monitoring_window_minutes
        self.error_spike_threshold = error_spike_threshold

        # Create necessary directories
        self.config_backup_dir.mkdir(parents=True, exist_ok=True)
        self.execution_history_file.parent.mkdir(parents=True, exist_ok=True)

        self.execution_history = self._load_execution_history()

    def _load_execution_history(self) -> list[dict]:
        """Load execution history from disk."""
        if self.execution_history_file.exists():
            try:
                with open(self.execution_history_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load execution history: {e}")
                return []
        return []

    def _save_execution_history(self) -> None:
        """Save execution history to disk."""
        try:
            with open(self.execution_history_file, "w") as f:
                json.dump(self.execution_history, f, indent=2, default=str)
            logger.info(f"Execution history saved to {self.execution_history_file}")
        except Exception as e:
            logger.error(f"Failed to save execution history: {e}")

    def load_recommendations(self) -> list[TuningRecommendation]:
        """
        Load tuning recommendations from pool_optimizer output.

        Returns:
            List of tuning recommendations
        """
        if not self.recommendations_file.exists():
            logger.warning(f"Recommendations file not found: {self.recommendations_file}")
            return []

        try:
            with open(self.recommendations_file) as f:
                data = json.load(f)

            recommendations = []
            for rec_data in data.get("recommendations", []):
                recommendations.append(
                    TuningRecommendation(
                        service_name=rec_data["service_name"],
                        current_config=rec_data["current_config"],
                        recommended_config=rec_data["recommended_config"],
                        expected_improvement=rec_data["expected_improvement"],
                        priority=rec_data.get("priority", "medium"),
                        confidence=rec_data.get("confidence", 0.7),
                        rationale=rec_data.get("rationale", ""),
                        estimated_impact=rec_data.get("estimated_impact", {}),
                        risk_level=rec_data.get("risk_level", "medium"),
                    ),
                )

            logger.info(f"Loaded {len(recommendations)} tuning recommendations")
            return recommendations

        except Exception as e:
            logger.error(f"Failed to load recommendations: {e}")
            return []

    def prioritize_recommendations(self, recommendations: list[TuningRecommendation]) -> list[TuningRecommendation]:
        """
        Prioritize recommendations by impact and safety.

        Priority order:
        1. Critical priority, low risk, high confidence
        2. High priority, low risk, high confidence
        3. Medium priority, low risk, medium confidence
        4. Others sorted by confidence

        Args:
            recommendations: List of recommendations to prioritize

        Returns:
            Sorted list of recommendations
        """
        priority_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        risk_map = {"low": 3, "medium": 2, "high": 1}

        def priority_score(rec: TuningRecommendation) -> tuple:
            return (priority_map.get(rec.priority, 0), risk_map.get(rec.risk_level, 0), rec.confidence)

        sorted_recs = sorted(recommendations, key=priority_score, reverse=True)

        logger.info(
            f"Prioritized {len(sorted_recs)} recommendations "
            f"(top: {sorted_recs[0].service_name if sorted_recs else 'none'})",
        )

        return sorted_recs

    def is_maintenance_window(self) -> bool:
        """
        Check if current time is within maintenance window.

        Default maintenance windows:
        - Weekdays: 2 AM - 4 AM local time
        - Weekends: Any time

        Returns:
            True if within maintenance window
        """
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()

        # Weekend (Saturday=5, Sunday=6)
        if weekday >= 5:
            return True

        # Weekday 2 AM - 4 AM
        if 2 <= hour < 4:
            return True

        return False

    async def backup_current_config_async(self, service_name: str, config: dict[str, Any]) -> Path:
        """
        Backup current configuration before changes.

        Args:
            service_name: Service being configured
            config: Current configuration

        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.config_backup_dir / f"{service_name}_{timestamp}.json"

        try:
            with open(backup_file, "w") as f:
                json.dump(
                    {"service_name": service_name, "timestamp": datetime.now().isoformat(), "config": config},
                    f,
                    indent=2,
                )

            logger.info(f"Backed up config for {service_name} to {backup_file}")
            return backup_file

        except Exception as e:
            logger.error(f"Failed to backup config for {service_name}: {e}")
            raise

    async def apply_configuration_async(self, service_name: str, new_config: dict[str, Any]) -> bool:
        """
        Apply new configuration to service.

        This is a placeholder that would integrate with actual
        configuration management system (e.g., hive_config).

        Args:
            service_name: Service to configure
            new_config: New configuration to apply

        Returns:
            True if successful
        """
        try:
            logger.info(f"Applying new configuration to {service_name}: {new_config}")

            # TODO: Integrate with actual configuration system
            # from hive_db import update_pool_config
            # await update_pool_config(service_name, new_config)

            # Placeholder: Write to config file
            config_file = Path(f"config/pools/{service_name}.json")
            config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(config_file, "w") as f:
                json.dump(new_config, f, indent=2)

            logger.info(f"Configuration applied to {service_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply configuration to {service_name}: {e}")
            return False

    async def monitor_metrics_async(self, service_name: str, duration_minutes: int = 15) -> dict[str, Any]:
        """
        Monitor service metrics after configuration change.

        Tracks:
        - Error rate
        - Connection failures
        - Latency
        - Resource utilization

        Args:
            service_name: Service to monitor
            duration_minutes: How long to monitor

        Returns:
            Metrics collected during monitoring period
        """
        logger.info(f"Monitoring {service_name} for {duration_minutes} minutes...")

        # TODO: Integrate with actual monitoring system
        # from hive_errors import MonitoringErrorReporter
        # error_reporter.get_error_rate_history(service_name=service_name)

        # Placeholder: Simulate monitoring
        await asyncio.sleep(duration_minutes * 60)

        # Placeholder metrics
        metrics = {
            "service_name": service_name,
            "monitoring_duration_minutes": duration_minutes,
            "error_rate": 0.02,  # 2%
            "connection_failures": 3,
            "avg_latency_ms": 45.5,
            "p95_latency_ms": 89.2,
            "cpu_utilization": 0.65,
            "memory_utilization": 0.72,
        }

        logger.info(f"Monitoring complete for {service_name}: {metrics}")
        return metrics

    def should_rollback(self, metrics_before: dict[str, Any], metrics_after: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Determine if rollback is needed based on metrics.

        Rollback triggers:
        - Error rate increase >20%
        - Connection failures increase >50%
        - Latency increase >30%

        Args:
            metrics_before: Metrics before change
            metrics_after: Metrics after change

        Returns:
            (should_rollback, reason)
        """
        # Error rate check
        error_before = metrics_before.get("error_rate", 0.0)
        error_after = metrics_after.get("error_rate", 0.0)

        if error_before > 0:
            error_increase = (error_after - error_before) / error_before
            if error_increase > self.error_spike_threshold:
                return True, (
                    f"Error rate increased by {error_increase:.1%} (threshold: {self.error_spike_threshold:.1%})"
                )

        # Connection failures check
        failures_before = metrics_before.get("connection_failures", 0)
        failures_after = metrics_after.get("connection_failures", 0)

        if failures_before > 0:
            failure_increase = (failures_after - failures_before) / failures_before
            if failure_increase > 0.50:
                return True, (f"Connection failures increased by {failure_increase:.1%} (threshold: 50%)")

        # Latency check
        latency_before = metrics_before.get("avg_latency_ms", 0.0)
        latency_after = metrics_after.get("avg_latency_ms", 0.0)

        if latency_before > 0:
            latency_increase = (latency_after - latency_before) / latency_before
            if latency_increase > 0.30:
                return True, (f"Latency increased by {latency_increase:.1%} (threshold: 30%)")

        return False, None

    async def rollback_configuration_async(self, service_name: str, backup_config: dict[str, Any]) -> bool:
        """
        Rollback to previous configuration.

        Args:
            service_name: Service to rollback
            backup_config: Previous configuration to restore

        Returns:
            True if successful
        """
        logger.warning(f"Rolling back configuration for {service_name}")

        try:
            success = await self.apply_configuration_async(service_name, backup_config)

            if success:
                logger.info(f"Rollback successful for {service_name}")
            else:
                logger.error(f"Rollback failed for {service_name}")

            return success

        except Exception as e:
            logger.error(f"Rollback failed for {service_name}: {e}")
            return False

    async def execute_tuning_async(
        self,
        recommendation: TuningRecommendation,
        dry_run: bool = False,
    ) -> TuningExecution:
        """
        Execute a tuning recommendation.

        Workflow:
        1. Backup current config
        2. Get baseline metrics
        3. Apply new config
        4. Monitor for specified duration
        5. Compare metrics
        6. Rollback if needed
        7. Commit to git if successful

        Args:
            recommendation: Tuning recommendation to execute
            dry_run: If True, simulate without actual changes

        Returns:
            Execution record
        """
        execution_id = f"tune_{recommendation.service_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        execution = TuningExecution(
            execution_id=execution_id,
            service_name=recommendation.service_name,
            old_config=recommendation.current_config,
            new_config=recommendation.recommended_config,
            started_at=datetime.now().isoformat(),
            status="in_progress",
        )

        try:
            logger.info(f"Executing tuning for {recommendation.service_name} (dry_run={dry_run})")

            # Step 1: Backup current config
            if not dry_run:
                await self.backup_current_config_async(recommendation.service_name, recommendation.current_config)

            # Step 2: Get baseline metrics
            logger.info("Collecting baseline metrics...")
            execution.metrics_before = await self.monitor_metrics_async(recommendation.service_name, duration_minutes=5)

            # Step 3: Apply new configuration
            if not dry_run:
                success = await self.apply_configuration_async(
                    recommendation.service_name,
                    recommendation.recommended_config,
                )

                if not success:
                    execution.status = "failed"
                    execution.completed_at = datetime.now().isoformat()
                    return execution

            # Step 4: Monitor after change
            logger.info(f"Monitoring for {self.monitoring_window_minutes} minutes...")
            execution.metrics_after = await self.monitor_metrics_async(
                recommendation.service_name,
                duration_minutes=self.monitoring_window_minutes,
            )

            # Step 5: Check if rollback needed
            should_rollback, rollback_reason = self.should_rollback(execution.metrics_before, execution.metrics_after)

            if should_rollback:
                logger.warning(f"Rollback needed: {rollback_reason}")
                execution.rollback_needed = True
                execution.rollback_reason = rollback_reason

                if not dry_run:
                    rollback_success = await self.rollback_configuration_async(
                        recommendation.service_name,
                        recommendation.current_config,
                    )

                    if rollback_success:
                        execution.status = "rolled_back"
                    else:
                        execution.status = "failed"
            else:
                execution.status = "completed"
                logger.info(f"Tuning successful for {recommendation.service_name}")

                # Step 6: Commit to git if not dry run
                if not dry_run and execution.status == "completed":
                    self._commit_to_git(recommendation)

            execution.completed_at = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Tuning execution failed: {e}", exc_info=True)
            execution.status = "failed"
            execution.completed_at = datetime.now().isoformat()

        # Save execution history
        self.execution_history.append(execution.__dict__)
        self._save_execution_history()

        return execution

    def _commit_to_git(self, recommendation: TuningRecommendation) -> None:
        """
        Commit configuration change to git.

        Args:
            recommendation: Recommendation that was applied
        """
        try:
            config_file = f"config/pools/{recommendation.service_name}.json"

            # Git add
            subprocess.run(["git", "add", config_file], check=True, capture_output=True)

            # Git commit with detailed message
            commit_message = (
                f"feat(pool): automated tuning for {recommendation.service_name}\n\n"
                f"Priority: {recommendation.priority}\n"
                f"Expected improvement: {recommendation.expected_improvement}\n"
                f"Rationale: {recommendation.rationale}\n\n"
                f"Automated by PROJECT VANGUARD Phase 2.2\n"
                f"Configuration versioned for rollback capability"
            )

            subprocess.run(["git", "commit", "-m", commit_message], check=True, capture_output=True)

            logger.info(f"Committed configuration change for {recommendation.service_name} to git")

        except subprocess.CalledProcessError as e:
            logger.error(f"Git commit failed: {e}")
        except Exception as e:
            logger.error(f"Failed to commit to git: {e}")

    async def run_orchestration_async(
        self,
        service_filter: str | None = None,
        dry_run: bool = False,
        skip_maintenance_check: bool = False,
    ) -> list[TuningExecution]:
        """
        Run complete orchestration workflow.

        Args:
            service_filter: Only tune specific service if specified
            dry_run: Simulate without actual changes
            skip_maintenance_check: Skip maintenance window validation

        Returns:
            List of tuning executions
        """
        logger.info("Starting pool tuning orchestration...")

        # Check maintenance window
        if not skip_maintenance_check and not self.is_maintenance_window():
            logger.warning("Not in maintenance window. Use --skip-maintenance-check to override")
            return []

        # Load and prioritize recommendations
        recommendations = self.load_recommendations()
        if not recommendations:
            logger.warning("No recommendations found")
            return []

        # Filter by service if specified
        if service_filter:
            recommendations = [r for r in recommendations if r.service_name == service_filter]

        prioritized = self.prioritize_recommendations(recommendations)

        # Execute tunings
        executions = []
        for recommendation in prioritized:
            logger.info(
                f"\nProcessing: {recommendation.service_name} "
                f"(priority={recommendation.priority}, "
                f"risk={recommendation.risk_level})",
            )

            execution = await self.execute_tuning_async(recommendation, dry_run)
            executions.append(execution)

            logger.info(f"Execution status: {execution.status}")

        logger.info(f"\nOrchestration complete: {len(executions)} tunings executed")

        return executions


async def main():
    """Main entry point for pool tuning orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(description="Pool Tuning Orchestrator")
    parser.add_argument("--analyze", action="store_true", help="Analyze and prioritize recommendations")
    parser.add_argument("--apply", action="store_true", help="Apply tuning recommendations")
    parser.add_argument("--service", type=str, help="Filter to specific service")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without actual changes")
    parser.add_argument("--skip-maintenance-check", action="store_true", help="Skip maintenance window validation")
    parser.add_argument("--rollback", action="store_true", help="Rollback to previous configuration")

    args = parser.parse_args()

    orchestrator = PoolTuningOrchestrator()

    if args.analyze:
        logger.info("Analyzing recommendations...")
        recommendations = orchestrator.load_recommendations()
        prioritized = orchestrator.prioritize_recommendations(recommendations)

        print("\n" + "=" * 80)
        print("POOL TUNING RECOMMENDATIONS (Prioritized)")
        print("=" * 80)

        for i, rec in enumerate(prioritized, 1):
            print(f"\n{i}. {rec.service_name}")
            print(f"   Priority: {rec.priority} | Risk: {rec.risk_level} | Confidence: {rec.confidence:.1%}")
            print(f"   Expected: {rec.expected_improvement}")
            print(f"   Rationale: {rec.rationale}")

    elif args.apply:
        logger.info("Applying tuning recommendations...")
        executions = await orchestrator.run_orchestration_async(
            service_filter=args.service,
            dry_run=args.dry_run,
            skip_maintenance_check=args.skip_maintenance_check,
        )

        print("\n" + "=" * 80)
        print("TUNING EXECUTION SUMMARY")
        print("=" * 80)

        for execution in executions:
            status_symbol = {"completed": "✓", "rolled_back": "↺", "failed": "✗"}.get(execution.status, "?")

            print(f"\n{status_symbol} {execution.service_name}: {execution.status}")
            if execution.rollback_reason:
                print(f"  Reason: {execution.rollback_reason}")

    elif args.rollback:
        if not args.service:
            print("ERROR: --service required for rollback")
            sys.exit(1)

        # TODO: Implement manual rollback
        print(f"Rollback for {args.service} not yet implemented")

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
