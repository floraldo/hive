"""
Health monitoring for AI models and providers.

Provides comprehensive health checks, availability monitoring
and performance degradation detection for AI infrastructure.
"""
from __future__ import annotations


import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, AnyCallable
from dataclasses import dataclass, field
from enum import Enum

from hive_logging import get_logger
from hive_cache import CacheManager
from hive_async import AsyncCircuitBreaker, async_timeout

from ..core.exceptions import ModelError, AIError
from ..models.registry import ModelRegistry


logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    status: HealthStatus
    response_time_ms: float
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class ProviderHealth:
    """Health status for an AI provider."""
    provider_name: str
    status: HealthStatus
    last_check: datetime
    response_time_ms: float
    availability_percentage: float
    error_rate: float
    recent_checks: List[HealthCheckResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelHealth:
    """Health status for a specific model."""
    model_name: str
    provider: str
    status: HealthStatus
    last_successful_request: datetime | None
    recent_error_count: int
    avg_response_time_ms: float
    success_rate: float
    performance_trend: str  # "improving", "stable", "degrading"


class ModelHealthChecker:
    """
    Comprehensive health monitoring for AI models and providers.

    Monitors availability, performance, and error rates with
    automated alerting and degradation detection.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        check_interval: int = 300,  # 5 minutes,
        degradation_threshold: float = 0.8,  # 80% success rate,
        unhealthy_threshold: float = 0.5   # 50% success rate
    ):
        self.registry = registry,
        self.check_interval = check_interval,
        self.degradation_threshold = degradation_threshold,
        self.unhealthy_threshold = unhealthy_threshold

        self.cache = CacheManager("model_health")

        # Health state storage,
        self._provider_health: Dict[str, ProviderHealth] = {},
        self._model_health: Dict[str, ModelHealth] = {}

        # Health check history,
        self._health_history: Dict[str, List[HealthCheckResult]] = {}

        # Monitoring state,
        self._monitoring_active = False,
        self._health_check_tasks: Dict[str, asyncio.Task] = {}

        # Health check configurations,
        self._health_check_configs = self._load_default_configs()

    def _load_default_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load default health check configurations for different providers."""
        return {
            "anthropic": {
                "timeout_seconds": 10,
                "test_prompt": "Hello, respond with 'OK' if you're working.",
                "expected_response_pattern": "OK",
                "max_response_time_ms": 5000,
                "min_success_rate": 0.9
            },
            "openai": {
                "timeout_seconds": 10,
                "test_prompt": "Say 'OK' to confirm you're operational.",
                "expected_response_pattern": "OK",
                "max_response_time_ms": 8000,
                "min_success_rate": 0.9
            },
            "local": {
                "timeout_seconds": 30,
                "test_prompt": "Respond with 'OK' if functional.",
                "expected_response_pattern": "OK",
                "max_response_time_ms": 15000,
                "min_success_rate": 0.8
            }
        }

    async def start_monitoring_async(self) -> None:
        """Start continuous health monitoring for all providers."""
        if self._monitoring_active:
            logger.warning("Health monitoring is already active")
            return

        self._monitoring_active = True

        # Get all providers from registry
        providers = set()
        for model_config in self.registry.config.models.values():
            providers.add(model_config.provider)

        # Start monitoring tasks for each provider
        for provider in providers:
            task = asyncio.create_task(
                self._monitor_provider_health_async(provider)
            )
            self._health_check_tasks[provider] = task

        logger.info(f"Started health monitoring for {len(providers)} providers")

    async def stop_monitoring_async(self) -> None:
        """Stop health monitoring."""
        self._monitoring_active = False

        # Cancel all monitoring tasks
        for provider, task in self._health_check_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._health_check_tasks.clear()
        logger.info("Stopped health monitoring")

    async def _monitor_provider_health_async(self, provider: str) -> None:
        """Continuously monitor health for a specific provider."""
        logger.info(f"Starting health monitoring for provider: {provider}")

        while self._monitoring_active:
            try:
                await self.check_provider_health_async(provider)
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error for {provider}: {e}")
                await asyncio.sleep(self.check_interval)

        logger.info(f"Stopped health monitoring for provider: {provider}")

    async def check_provider_health_async(self, provider: str) -> ProviderHealth:
        """
        Perform comprehensive health check for a provider.

        Args:
            provider: Provider name to check

        Returns:
            ProviderHealth with current status

        Raises:
            AIError: Health check failed
        """
        start_time = time.time()

        try:
            # Get provider instance
            provider_instance = self.registry.get_provider(provider)
            config = self._health_check_configs.get(provider, {})

            # Perform basic connectivity check
            connectivity_result = await self._check_connectivity_async(
                provider_instance,
                config
            )

            # Perform functional test
            functional_result = await self._check_functionality_async(
                provider,
                provider_instance,
                config
            )

            # Calculate overall health
            response_time_ms = (time.time() - start_time) * 1000
            overall_status = self._determine_provider_status(
                connectivity_result,
                functional_result
            )

            # Update health state
            health = self._update_provider_health(
                provider,
                overall_status,
                response_time_ms,
                {
                    "connectivity": connectivity_result.__dict__,
                    "functionality": functional_result.__dict__
                }
            )

            logger.debug(
                f"Provider health check completed: {provider} = {overall_status.value} ",
                f"({response_time_ms:.1f}ms)"
            )

            return health

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000

            # Record failed health check
            health = self._update_provider_health(
                provider,
                HealthStatus.UNHEALTHY,
                response_time_ms,
                {"error": str(e)}
            )

            logger.error(f"Provider health check failed: {provider} - {e}")
            return health

    async def _check_connectivity_async(
        self,
        provider_instance: Any,
        config: Dict[str, Any]
    ) -> HealthCheckResult:
        """Check basic connectivity to provider."""
        start_time = time.time()

        try:
            # Use provider's built-in health check if available
            if hasattr(provider_instance, 'validate_connection'):
                timeout_seconds = config.get("timeout_seconds", 10)

                async with async_timeout(timeout_seconds):
                    is_healthy = provider_instance.validate_connection()

                response_time_ms = (time.time() - start_time) * 1000

                return HealthCheckResult(
                    status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
                    response_time_ms=response_time_ms,
                    timestamp=datetime.utcnow(),
                    details={"check_type": "connectivity"}
                )

            else:
                # No connectivity check available
                return HealthCheckResult(
                    status=HealthStatus.UNKNOWN,
                    response_time_ms=0,
                    timestamp=datetime.utcnow(),
                    details={"check_type": "connectivity", "method": "unavailable"}
                )

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.utcnow(),
                details={"check_type": "connectivity"},
                error_message=str(e)
            )

    async def _check_functionality_async(
        self,
        provider_name: str,
        provider_instance: Any,
        config: Dict[str, Any]
    ) -> HealthCheckResult:
        """Check functional capability of provider."""
        start_time = time.time()

        try:
            # Get a test model for this provider
            test_model = self._get_test_model(provider_name)
            if not test_model:
                return HealthCheckResult(
                    status=HealthStatus.UNKNOWN,
                    response_time_ms=0,
                    timestamp=datetime.utcnow(),
                    details={"check_type": "functional", "reason": "no_test_model"}
                )

            # Perform test generation
            test_prompt = config.get("test_prompt", "Hello")
            timeout_seconds = config.get("timeout_seconds", 10)

            async with async_timeout(timeout_seconds):
                response = await provider_instance.generate_async(
                    test_prompt,
                    test_model
                )

            response_time_ms = (time.time() - start_time) * 1000

            # Validate response
            expected_pattern = config.get("expected_response_pattern")
            is_valid_response = (
                response and
                hasattr(response, 'content') and
                response.content and
                (not expected_pattern or expected_pattern.lower() in response.content.lower())
            )

            # Check performance thresholds
            max_response_time = config.get("max_response_time_ms", 10000)
            is_performant = response_time_ms <= max_response_time

            status = HealthStatus.HEALTHY
            if not is_valid_response:
                status = HealthStatus.UNHEALTHY
            elif not is_performant:
                status = HealthStatus.DEGRADED

            return HealthCheckResult(
                status=status,
                response_time_ms=response_time_ms,
                timestamp=datetime.utcnow(),
                details={
                    "check_type": "functional",
                    "test_model": test_model,
                    "response_valid": is_valid_response,
                    "performance_ok": is_performant,
                    "response_length": len(response.content) if response and response.content else 0,
                }
            )

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.utcnow(),
                details={"check_type": "functional"},
                error_message=str(e)
            )

    def _get_test_model(self, provider: str) -> str | None:
        """Get a suitable test model for the provider."""
        provider_models = [
            name for name, config in self.registry.config.models.items()
            if config.provider == provider
        ]

        if not provider_models:
            return None

        # Prefer completion or chat models for testing
        for model_name in provider_models:
            config = self.registry.config.models[model_name]
            if config.model_type in ["completion", "chat"]:
                return config.name

        # Fallback to first available model
        return self.registry.config.models[provider_models[0]].name

    def _determine_provider_status(
        self,
        connectivity: HealthCheckResult,
        functionality: HealthCheckResult
    ) -> HealthStatus:
        """Determine overall provider status from check results."""
        # If either check is unhealthy, provider is unhealthy,
        if (connectivity.status == HealthStatus.UNHEALTHY or
            functionality.status == HealthStatus.UNHEALTHY):
            return HealthStatus.UNHEALTHY

        # If either check is degraded, provider is degraded,
        if (connectivity.status == HealthStatus.DEGRADED or
            functionality.status == HealthStatus.DEGRADED):
            return HealthStatus.DEGRADED

        # If either check is unknown, provider status is degraded,
        if (connectivity.status == HealthStatus.UNKNOWN or
            functionality.status == HealthStatus.UNKNOWN):
            return HealthStatus.DEGRADED

        # Both checks are healthy,
        return HealthStatus.HEALTHY

    def _update_provider_health(
        self,
        provider: str,
        status: HealthStatus,
        response_time_ms: float,
        details: Dict[str, Any]
    ) -> ProviderHealth:
        """Update provider health state and history."""
        now = datetime.utcnow()

        # Create health check result,
        check_result = HealthCheckResult(
            status=status,
            response_time_ms=response_time_ms,
            timestamp=now,
            details=details
        )

        # Update history,
        if provider not in self._health_history:
            self._health_history[provider] = []

        self._health_history[provider].append(check_result)

        # Keep only recent history (last 100 checks)
        if len(self._health_history[provider]) > 100:
            self._health_history[provider] = self._health_history[provider][-100:]

        # Calculate availability and error rate,
        recent_checks = self._health_history[provider][-20:]  # Last 20 checks,
        availability = self._calculate_availability(recent_checks)
        error_rate = self._calculate_error_rate(recent_checks)

        # Update or create provider health,
        if provider not in self._provider_health:
            self._provider_health[provider] = ProviderHealth(
                provider_name=provider,
                status=status,
                last_check=now,
                response_time_ms=response_time_ms,
                availability_percentage=availability,
                error_rate=error_rate,
                recent_checks=recent_checks[-5:],  # Keep last 5 for details,
                metadata=details
            )
        else:
            health = self._provider_health[provider],
            health.status = status,
            health.last_check = now,
            health.response_time_ms = response_time_ms,
            health.availability_percentage = availability,
            health.error_rate = error_rate,
            health.recent_checks = recent_checks[-5:],
            health.metadata = details

        return self._provider_health[provider]

    def _calculate_availability(self, checks: List[HealthCheckResult]) -> float:
        """Calculate availability percentage from health checks."""
        if not checks:
            return 0.0

        healthy_checks = sum(
            1 for check in checks
            if check.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        )

        return (healthy_checks / len(checks)) * 100

    def _calculate_error_rate(self, checks: List[HealthCheckResult]) -> float:
        """Calculate error rate from health checks."""
        if not checks:
            return 0.0

        error_checks = sum(
            1 for check in checks
            if check.status == HealthStatus.UNHEALTHY
        )

        return (error_checks / len(checks))

    async def check_model_health_async(self, model_name: str) -> ModelHealth:
        """
        Check health status for a specific model.

        Args:
            model_name: Name of model to check

        Returns:
            ModelHealth with current status

        Raises:
            AIError: Model health check failed,
        """
        try:
            # Get model configuration,
            model_config = self.registry.get_model_config(model_name)

            # Check provider health first,
            provider_health = await self.check_provider_health_async(model_config.provider)

            # Model health is derived from provider health and model-specific metrics,
            model_status = self._determine_model_status(provider_health, model_name)

            # Update model health tracking,
            health = ModelHealth(
                model_name=model_name,
                provider=model_config.provider,
                status=model_status,
                last_successful_request=None,  # Would track from metrics,
                recent_error_count=0,  # Would track from metrics,
                avg_response_time_ms=provider_health.response_time_ms,
                success_rate=provider_health.availability_percentage / 100,
                performance_trend="stable"  # Would analyze from historical data
            )

            self._model_health[model_name] = health,
            return health

        except Exception as e:
            raise AIError(
                f"Model health check failed for '{model_name}': {str(e)}"
            ) from e

    def _determine_model_status(
        self,
        provider_health: ProviderHealth,
        model_name: str
    ) -> HealthStatus:
        """Determine model status based on provider health and model-specific factors."""
        # Model health is primarily based on provider health,
        # In a more sophisticated implementation, this would also consider:
        # - Model-specific error rates,
        # - Model performance compared to other models,
        # - Model availability vs provider availability

        return provider_health.status

    def get_overall_health_async(self) -> Dict[str, Any]:
        """Get comprehensive health status for all monitored components."""
        now = datetime.utcnow()

        # Provider health summary
        provider_summary = {}
        for provider, health in self._provider_health.items():
            provider_summary[provider] = {
                "status": health.status.value,
                "availability": health.availability_percentage,
                "last_check": health.last_check.isoformat(),
                "response_time_ms": health.response_time_ms
            }

        # Model health summary
        model_summary = {}
        for model, health in self._model_health.items():
            model_summary[model] = {
                "status": health.status.value,
                "provider": health.provider,
                "success_rate": health.success_rate,
                "avg_response_time_ms": health.avg_response_time_ms
            }

        # Overall system health
        healthy_providers = sum(
            1 for health in self._provider_health.values()
            if health.status == HealthStatus.HEALTHY
        )

        total_providers = len(self._provider_health)
        system_health = HealthStatus.HEALTHY

        if total_providers == 0:
            system_health = HealthStatus.UNKNOWN
        elif healthy_providers / total_providers < self.unhealthy_threshold:
            system_health = HealthStatus.UNHEALTHY
        elif healthy_providers / total_providers < self.degradation_threshold:
            system_health = HealthStatus.DEGRADED

        return {
            "overall_status": system_health.value,
            "timestamp": now.isoformat(),
            "monitoring_active": self._monitoring_active,
            "providers": provider_summary,
            "models": model_summary,
            "statistics": {
                "total_providers": total_providers,
                "healthy_providers": healthy_providers,
                "degraded_providers": sum(
                    1 for health in self._provider_health.values()
                    if health.status == HealthStatus.DEGRADED
                ),
                "unhealthy_providers": sum(
                    1 for health in self._provider_health.values()
                    if health.status == HealthStatus.UNHEALTHY
                ),
                "avg_availability": (
                    sum(health.availability_percentage for health in self._provider_health.values()) /
                    total_providers if total_providers > 0 else 0
                )
            }
        }

    async def get_health_alerts_async(self) -> List[Dict[str, Any]]:
        """Get current health alerts requiring attention."""
        alerts = []

        for provider, health in self._provider_health.items():
            # Unhealthy provider alert
            if health.status == HealthStatus.UNHEALTHY:
                alerts.append({
                    "type": "provider_unhealthy",
                    "severity": "critical",
                    "provider": provider,
                    "message": f"Provider {provider} is unhealthy",
                    "details": health.metadata,
                    "timestamp": health.last_check.isoformat()
                })

            # Low availability alert
            elif health.availability_percentage < 80:
                alerts.append({
                    "type": "low_availability",
                    "severity": "warning",
                    "provider": provider,
                    "message": f"Provider {provider} availability is {health.availability_percentage:.1f}%",
                    "availability": health.availability_percentage,
                    "timestamp": health.last_check.isoformat()
                })

            # High response time alert
            elif health.response_time_ms > 10000:
                alerts.append({
                    "type": "high_latency",
                    "severity": "warning",
                    "provider": provider,
                    "message": f"Provider {provider} response time is {health.response_time_ms:.1f}ms",
                    "response_time_ms": health.response_time_ms,
                    "timestamp": health.last_check.isoformat()
                })

        return alerts

    def get_metric_history(
        self,
        provider: str,
        metric_name: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get historical health metrics for predictive analysis.

        Returns health metrics as MetricPoint-compatible format for
        integration with PredictiveAnalysisRunner.

        Args:
            provider: Provider name to get metrics for
            metric_name: Metric type (response_time, availability, error_rate)
            hours: Number of hours of history to return

        Returns:
            List of metric points with timestamp, value, and metadata
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        # Get health check history for provider
        if provider not in self._health_history:
            logger.debug(f"No health history available for provider: {provider}")
            return []

        # Filter to recent history
        recent_checks = [
            check for check in self._health_history[provider]
            if check.timestamp >= cutoff_time
        ]

        if not recent_checks:
            logger.debug(f"No recent health checks for {provider} in last {hours} hours")
            return []

        # Extract requested metric from health checks
        metric_points = []
        for check in recent_checks:
            value = None

            if metric_name == "response_time":
                value = check.response_time_ms
            elif metric_name == "availability":
                # Convert status to availability value (1.0 = healthy, 0.5 = degraded, 0.0 = unhealthy)
                if check.status == HealthStatus.HEALTHY:
                    value = 1.0
                elif check.status == HealthStatus.DEGRADED:
                    value = 0.5
                elif check.status == HealthStatus.UNHEALTHY:
                    value = 0.0
                else:
                    value = 0.0  # UNKNOWN treated as unavailable
            elif metric_name == "error_rate":
                # Binary: 1.0 if unhealthy, 0.0 otherwise
                value = 1.0 if check.status == HealthStatus.UNHEALTHY else 0.0
            elif metric_name == "cpu_percent" or metric_name == "memory_percent":
                # Extract from details if available
                value = check.details.get(metric_name)
            else:
                logger.warning(f"Unknown metric type: {metric_name}")
                continue

            if value is not None:
                metric_points.append({
                    "timestamp": check.timestamp,
                    "value": float(value),
                    "metadata": {
                        "provider": provider,
                        "metric_type": metric_name,
                        "check_status": check.status.value,
                        "unit": self._get_metric_unit(metric_name)
                    }
                })

        logger.debug(
            f"Retrieved {len(metric_points)} health metric points for "
            f"provider={provider}, metric={metric_name}"
        )

        return metric_points

    def _get_metric_unit(self, metric_name: str) -> str:
        """Get appropriate unit for metric type."""
        units = {
            "response_time": "milliseconds",
            "availability": "ratio",
            "error_rate": "ratio",
            "cpu_percent": "percentage",
            "memory_percent": "percentage"
        }
        return units.get(metric_name, "unknown")

    async def close_async(self) -> None:
        """Close health checker and clean up resources."""
        await self.stop_monitoring_async()
        self.cache.clear()
        logger.info("Model health checker closed")
