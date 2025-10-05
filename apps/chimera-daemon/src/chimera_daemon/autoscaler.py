"""Dynamic Pool Autoscaling for ExecutorPool.

Automatically adjusts pool size based on queue depth, utilization, and latency trends.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from hive_logging import get_logger

from .metrics import PoolMetrics

logger = get_logger(__name__)


class ScalingDirection(Enum):
    """Pool scaling direction."""

    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"


@dataclass
class ScalingPolicy:
    """Autoscaling policy configuration."""

    min_pool_size: int = 2
    max_pool_size: int = 10
    target_utilization: float = 0.7  # 70% target
    scale_up_threshold: float = 0.85  # Scale up above 85%
    scale_down_threshold: float = 0.5  # Scale down below 50%
    cooldown_seconds: float = 60.0  # Wait 60s between scaling actions
    scale_up_increment: int = 2  # Add 2 executors at a time
    scale_down_decrement: int = 1  # Remove 1 executor at a time
    queue_depth_threshold: int = 10  # Trigger scale-up if queue > 10

    def __post_init__(self):
        """Validate policy configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.min_pool_size < 1:
            raise ValueError(f"min_pool_size must be >= 1, got {self.min_pool_size}")

        if self.max_pool_size < self.min_pool_size:
            raise ValueError(
                f"max_pool_size ({self.max_pool_size}) must be >= "
                f"min_pool_size ({self.min_pool_size})"
            )

        if not (0.0 < self.target_utilization < 1.0):
            raise ValueError(f"target_utilization must be 0.0-1.0, got {self.target_utilization}")

        if not (0.0 < self.scale_up_threshold <= 1.0):
            raise ValueError(f"scale_up_threshold must be 0.0-1.0, got {self.scale_up_threshold}")

        if not (0.0 <= self.scale_down_threshold < 1.0):
            raise ValueError(f"scale_down_threshold must be 0.0-1.0, got {self.scale_down_threshold}")

        if self.scale_down_threshold >= self.scale_up_threshold:
            raise ValueError(
                f"scale_down_threshold ({self.scale_down_threshold}) must be < "
                f"scale_up_threshold ({self.scale_up_threshold})"
            )

        if self.cooldown_seconds < 0:
            raise ValueError(f"cooldown_seconds must be >= 0, got {self.cooldown_seconds}")

        if self.scale_up_increment < 1:
            raise ValueError(f"scale_up_increment must be >= 1, got {self.scale_up_increment}")

        if self.scale_down_decrement < 1:
            raise ValueError(f"scale_down_decrement must be >= 1, got {self.scale_down_decrement}")

        if self.queue_depth_threshold < 0:
            raise ValueError(f"queue_depth_threshold must be >= 0, got {self.queue_depth_threshold}")


@dataclass
class ScalingDecision:
    """Autoscaling decision with rationale."""

    direction: ScalingDirection
    current_size: int
    target_size: int
    reason: str
    triggered_by: str  # "utilization" | "queue_depth" | "latency" | "cooldown"
    timestamp: datetime


class PoolAutoscaler:
    """Dynamic pool autoscaler with intelligent scaling decisions.

    Monitors pool metrics and automatically scales up/down based on:
    - Pool utilization
    - Queue depth
    - Latency trends
    - Historical patterns

    Example:
        policy = ScalingPolicy(min_pool_size=2, max_pool_size=20)
        autoscaler = PoolAutoscaler(policy=policy)

        # Check if scaling needed
        decision = autoscaler.evaluate_scaling(
            metrics=pool_metrics,
            current_pool_size=5,
        )

        if decision.direction == ScalingDirection.SCALE_UP:
            await executor_pool.resize_pool(decision.target_size)
    """

    def __init__(self, policy: ScalingPolicy | None = None):
        """Initialize pool autoscaler.

        Args:
            policy: Scaling policy configuration
        """
        self.policy = policy or ScalingPolicy()
        self.logger = logger

        # Scaling state
        self._last_scaling_action: datetime | None = None
        self._scaling_history: list[ScalingDecision] = []
        self._max_history = 100

    def evaluate_scaling(
        self,
        metrics: PoolMetrics,
        current_pool_size: int,
    ) -> ScalingDecision:
        """Evaluate if scaling is needed based on current metrics.

        Args:
            metrics: Current pool metrics
            current_pool_size: Current pool size

        Returns:
            Scaling decision with rationale
        """
        # Check cooldown period
        if self._is_in_cooldown():
            return ScalingDecision(
                direction=ScalingDirection.MAINTAIN,
                current_size=current_pool_size,
                target_size=current_pool_size,
                reason="Cooldown period active",
                triggered_by="cooldown",
                timestamp=datetime.now(),
            )

        # Evaluate scaling triggers
        utilization_decision = self._evaluate_utilization(metrics, current_pool_size)
        queue_decision = self._evaluate_queue_depth(metrics, current_pool_size)
        latency_decision = self._evaluate_latency(metrics, current_pool_size)

        # Priority: queue depth > utilization > latency
        decisions = [queue_decision, utilization_decision, latency_decision]

        # Find first non-MAINTAIN decision
        for decision in decisions:
            if decision.direction != ScalingDirection.MAINTAIN:
                self._record_decision(decision)
                return decision

        # Default: maintain
        maintain_decision = ScalingDecision(
            direction=ScalingDirection.MAINTAIN,
            current_size=current_pool_size,
            target_size=current_pool_size,
            reason="Metrics within acceptable range",
            triggered_by="none",
            timestamp=datetime.now(),
        )
        return maintain_decision

    def _evaluate_utilization(
        self, metrics: PoolMetrics, current_pool_size: int
    ) -> ScalingDecision:
        """Evaluate scaling based on pool utilization.

        Args:
            metrics: Current pool metrics
            current_pool_size: Current pool size

        Returns:
            Scaling decision
        """
        utilization = metrics.pool_utilization_pct / 100.0

        # Scale up if utilization too high
        if utilization >= self.policy.scale_up_threshold:
            if current_pool_size >= self.policy.max_pool_size:
                return ScalingDecision(
                    direction=ScalingDirection.MAINTAIN,
                    current_size=current_pool_size,
                    target_size=current_pool_size,
                    reason=f"At max pool size ({self.policy.max_pool_size})",
                    triggered_by="utilization",
                    timestamp=datetime.now(),
                )

            target_size = min(
                current_pool_size + self.policy.scale_up_increment,
                self.policy.max_pool_size,
            )

            return ScalingDecision(
                direction=ScalingDirection.SCALE_UP,
                current_size=current_pool_size,
                target_size=target_size,
                reason=f"High utilization: {utilization:.1%} >= {self.policy.scale_up_threshold:.1%}",
                triggered_by="utilization",
                timestamp=datetime.now(),
            )

        # Scale down if utilization too low
        if utilization <= self.policy.scale_down_threshold:
            if current_pool_size <= self.policy.min_pool_size:
                return ScalingDecision(
                    direction=ScalingDirection.MAINTAIN,
                    current_size=current_pool_size,
                    target_size=current_pool_size,
                    reason=f"At min pool size ({self.policy.min_pool_size})",
                    triggered_by="utilization",
                    timestamp=datetime.now(),
                )

            target_size = max(
                current_pool_size - self.policy.scale_down_decrement,
                self.policy.min_pool_size,
            )

            return ScalingDecision(
                direction=ScalingDirection.SCALE_DOWN,
                current_size=current_pool_size,
                target_size=target_size,
                reason=f"Low utilization: {utilization:.1%} <= {self.policy.scale_down_threshold:.1%}",
                triggered_by="utilization",
                timestamp=datetime.now(),
            )

        # Maintain current size
        return ScalingDecision(
            direction=ScalingDirection.MAINTAIN,
            current_size=current_pool_size,
            target_size=current_pool_size,
            reason=f"Utilization within target range: {utilization:.1%}",
            triggered_by="utilization",
            timestamp=datetime.now(),
        )

    def _evaluate_queue_depth(
        self, metrics: PoolMetrics, current_pool_size: int
    ) -> ScalingDecision:
        """Evaluate scaling based on queue depth.

        Args:
            metrics: Current pool metrics
            current_pool_size: Current pool size

        Returns:
            Scaling decision
        """
        # Scale up if queue is growing and deep
        if (
            metrics.queue_depth >= self.policy.queue_depth_threshold
            and metrics.queue_depth_trend == "increasing"
        ):
            if current_pool_size >= self.policy.max_pool_size:
                return ScalingDecision(
                    direction=ScalingDirection.MAINTAIN,
                    current_size=current_pool_size,
                    target_size=current_pool_size,
                    reason=f"At max pool size ({self.policy.max_pool_size})",
                    triggered_by="queue_depth",
                    timestamp=datetime.now(),
                )

            target_size = min(
                current_pool_size + self.policy.scale_up_increment,
                self.policy.max_pool_size,
            )

            return ScalingDecision(
                direction=ScalingDirection.SCALE_UP,
                current_size=current_pool_size,
                target_size=target_size,
                reason=f"Queue depth {metrics.queue_depth} >= {self.policy.queue_depth_threshold} and increasing",
                triggered_by="queue_depth",
                timestamp=datetime.now(),
            )

        # Scale down if queue is empty and stable
        if metrics.queue_depth == 0 and metrics.queue_depth_trend == "stable":
            if current_pool_size <= self.policy.min_pool_size:
                return ScalingDecision(
                    direction=ScalingDirection.MAINTAIN,
                    current_size=current_pool_size,
                    target_size=current_pool_size,
                    reason=f"At min pool size ({self.policy.min_pool_size})",
                    triggered_by="queue_depth",
                    timestamp=datetime.now(),
                )

            # Only scale down gradually
            target_size = max(
                current_pool_size - self.policy.scale_down_decrement,
                self.policy.min_pool_size,
            )

            return ScalingDecision(
                direction=ScalingDirection.SCALE_DOWN,
                current_size=current_pool_size,
                target_size=target_size,
                reason="Queue empty and stable",
                triggered_by="queue_depth",
                timestamp=datetime.now(),
            )

        return ScalingDecision(
            direction=ScalingDirection.MAINTAIN,
            current_size=current_pool_size,
            target_size=current_pool_size,
            reason=f"Queue depth {metrics.queue_depth} within acceptable range",
            triggered_by="queue_depth",
            timestamp=datetime.now(),
        )

    def _evaluate_latency(
        self, metrics: PoolMetrics, current_pool_size: int
    ) -> ScalingDecision:
        """Evaluate scaling based on latency trends.

        Args:
            metrics: Current pool metrics
            current_pool_size: Current pool size

        Returns:
            Scaling decision
        """
        # Scale up if latency is increasing significantly
        if metrics.latency_trend == "increasing" and metrics.p95_workflow_duration_ms > 0:
            # Check if P95 latency is significantly higher than P50
            if metrics.p95_workflow_duration_ms > metrics.p50_workflow_duration_ms * 2:
                if current_pool_size >= self.policy.max_pool_size:
                    return ScalingDecision(
                        direction=ScalingDirection.MAINTAIN,
                        current_size=current_pool_size,
                        target_size=current_pool_size,
                        reason=f"At max pool size ({self.policy.max_pool_size})",
                        triggered_by="latency",
                        timestamp=datetime.now(),
                    )

                target_size = min(
                    current_pool_size + self.policy.scale_up_increment,
                    self.policy.max_pool_size,
                )

                p95 = metrics.p95_workflow_duration_ms
                p50 = metrics.p50_workflow_duration_ms
                return ScalingDecision(
                    direction=ScalingDirection.SCALE_UP,
                    current_size=current_pool_size,
                    target_size=target_size,
                    reason=f"Increasing latency: P95={p95:.0f}ms, P50={p50:.0f}ms",
                    triggered_by="latency",
                    timestamp=datetime.now(),
                )

        return ScalingDecision(
            direction=ScalingDirection.MAINTAIN,
            current_size=current_pool_size,
            target_size=current_pool_size,
            reason="Latency within acceptable range",
            triggered_by="latency",
            timestamp=datetime.now(),
        )

    def _is_in_cooldown(self) -> bool:
        """Check if autoscaler is in cooldown period.

        Returns:
            True if in cooldown, False otherwise
        """
        if self._last_scaling_action is None:
            return False

        elapsed = (datetime.now() - self._last_scaling_action).total_seconds()
        return elapsed < self.policy.cooldown_seconds

    def _record_decision(self, decision: ScalingDecision) -> None:
        """Record a scaling decision for history.

        Args:
            decision: Scaling decision to record
        """
        if decision.direction != ScalingDirection.MAINTAIN:
            self._last_scaling_action = decision.timestamp

        self._scaling_history.append(decision)

        # Trim history
        if len(self._scaling_history) > self._max_history:
            self._scaling_history = self._scaling_history[-self._max_history :]

        self.logger.info(
            f"Scaling decision: {decision.direction.value}",
            extra={
                "current_size": decision.current_size,
                "target_size": decision.target_size,
                "reason": decision.reason,
                "triggered_by": decision.triggered_by,
            },
        )

    def get_scaling_history(self, limit: int = 10) -> list[ScalingDecision]:
        """Get recent scaling decisions.

        Args:
            limit: Number of recent decisions to return

        Returns:
            List of recent scaling decisions
        """
        return self._scaling_history[-limit:]

    def get_scaling_metrics(self) -> dict[str, Any]:
        """Get autoscaling metrics.

        Returns:
            Dictionary with autoscaling statistics
        """
        scale_ups = sum(
            1 for d in self._scaling_history if d.direction == ScalingDirection.SCALE_UP
        )
        scale_downs = sum(
            1 for d in self._scaling_history if d.direction == ScalingDirection.SCALE_DOWN
        )

        return {
            "total_scaling_actions": scale_ups + scale_downs,
            "scale_ups": scale_ups,
            "scale_downs": scale_downs,
            "last_scaling_action": (
                self._last_scaling_action.isoformat() if self._last_scaling_action else None
            ),
            "cooldown_seconds_remaining": (
                max(
                    0,
                    self.policy.cooldown_seconds
                    - (datetime.now() - self._last_scaling_action).total_seconds(),
                )
                if self._last_scaling_action
                else 0
            ),
            "policy": {
                "min_pool_size": self.policy.min_pool_size,
                "max_pool_size": self.policy.max_pool_size,
                "target_utilization": self.policy.target_utilization,
            },
        }


__all__ = ["PoolAutoscaler", "ScalingPolicy", "ScalingDecision", "ScalingDirection"]
