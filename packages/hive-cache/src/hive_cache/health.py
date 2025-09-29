"""Health monitoring and diagnostics for Hive Cache."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List

from hive_logging import get_logger

from .cache_client import HiveCacheClient
from .config import CacheConfig
from .exceptions import CacheConnectionError, CacheError

logger = get_logger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    healthy: bool
    timestamp: datetime
    response_time_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class PerformanceMetrics:
    """Performance metrics for cache operations."""
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    average_response_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    connection_pool_usage: float = 0.0
    memory_usage_bytes: int = 0


class CacheHealthMonitor:
    """
    Comprehensive health monitoring for Hive Cache.

    Features:
    - Continuous health checks with configurable intervals
    - Performance metrics collection and analysis
    - Alert generation for critical issues
    - Health history tracking
    - Redis server monitoring
    - Connection pool monitoring
    """

    def __init__(self, cache_client: HiveCacheClient, config: CacheConfig) -> None:
        self.cache_client = cache_client
        self.config = config
        self._monitoring_active = False
        self._health_history: List[HealthCheckResult] = []
        self._max_history_size = 100
        self._alert_thresholds = {
            "response_time_ms": 1000,  # Alert if response time > 1s,
            "error_rate_percent": 10,  # Alert if error rate > 10%,
            "consecutive_failures": 3,  # Alert after 3 consecutive failures
        }
        self._consecutive_failures = 0

    async def start_monitoring_async(self) -> None:
        """Start continuous health monitoring."""
        if self._monitoring_active:
            logger.warning("Health monitoring already active")
            return

        self._monitoring_active = True
        logger.info("Starting cache health monitoring")

        # Start monitoring task
        asyncio.create_task(self._monitoring_loop_async())

    async def stop_monitoring_async(self) -> None:
        """Stop continuous health monitoring."""
        self._monitoring_active = False
        logger.info("Stopped cache health monitoring")

    async def _monitoring_loop_async(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                # Perform health check
                health_result = await self.perform_health_check_async()

                # Store in history
                self._add_to_history(health_result)

                # Check for alerts
                await self._check_alerts_async(health_result)

                # Sleep until next check
                await asyncio.sleep(self.config.health_check_interval)

            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(self.config.health_check_interval)

    def _add_to_history(self, result: HealthCheckResult) -> None:
        """Add health check result to history."""
        self._health_history.append(result)

        # Maintain max history size
        if len(self._health_history) > self._max_history_size:
            self._health_history.pop(0)

    async def _check_alerts_async(self, result: HealthCheckResult) -> None:
        """Check if alerts should be generated."""
        alerts = []

        # Check response time
        if result.response_time_ms > self._alert_thresholds["response_time_ms"]:
            alerts.append(f"High response time: {result.response_time_ms:.2f}ms")

        # Check for failures
        if not result.healthy:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._alert_thresholds["consecutive_failures"]:
                alerts.append(f"Consecutive failures: {self._consecutive_failures}")
        else:
            self._consecutive_failures = 0

        # Check error rate over recent history
        if len(self._health_history) >= 10:
            recent_checks = self._health_history[-10:]
            failed_checks = sum(1 for check in recent_checks if not check.healthy)
            error_rate = (failed_checks / len(recent_checks)) * 100

            if error_rate > self._alert_thresholds["error_rate_percent"]:
                alerts.append(f"High error rate: {error_rate:.1f}%")

        # Log alerts
        for alert in alerts:
            logger.warning(f"Cache health alert: {alert}")

    async def perform_health_check_async(self) -> HealthCheckResult:
        """Perform comprehensive health check.

        Returns:
            HealthCheckResult with detailed status
        """
        start_time = time.time()
        errors = []
        details = {}

        try:
            # Test basic connectivity
            ping_result = await self._test_ping_async()
            details["ping"] = ping_result

            # Test set/get operations
            set_get_result = await self._test_set_get_async()
            details["set_get"] = set_get_result

            # Test pattern operations
            pattern_result = await self._test_pattern_operations_async()
            details["pattern_operations"] = pattern_result

            # Get Redis info
            redis_info = await self._get_redis_info_async()
            details["redis_info"] = redis_info

            # Get connection pool stats
            pool_stats = await self._get_connection_pool_stats_async()
            details["connection_pool"] = pool_stats

            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000

            # Determine overall health
            healthy = all([
                ping_result.get("success", False),
                set_get_result.get("success", False),
                pattern_result.get("success", False),
            ])

            return HealthCheckResult(
                healthy=healthy,
                timestamp=datetime.utcnow()
                response_time_ms=response_time_ms,
                details=details
                errors=errors
            )

        except Exception as e:
            errors.append(str(e))
            response_time_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                healthy=False,
                timestamp=datetime.utcnow()
                response_time_ms=response_time_ms,
                details=details
                errors=errors
            )

    async def _test_ping_async(self) -> Dict[str, Any]:
        """Test Redis ping operation."""
        try:
            import aioredis
            async with aioredis.Redis(connection_pool=self.cache_client._redis_pool) as redis:
                start_time = time.time()
                result = await redis.ping()
                ping_time = (time.time() - start_time) * 1000

                return {
                    "success": True,
                    "result": result
                    "ping_time_ms": ping_time
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _test_set_get_async(self) -> Dict[str, Any]:
        """Test set/get operations."""
        try:
            test_key = f"health_check_{int(time.time())}"
            test_value = {"test": True, "timestamp": time.time()}

            # Test set
            set_success = await self.cache_client.set(
                test_key, test_value, ttl=60, namespace="health"
            )

            # Test get
            retrieved_value = await self.cache_client.get(test_key, namespace="health")

            # Test delete
            delete_success = await self.cache_client.delete(test_key, namespace="health")

            return {
                "success": set_success and retrieved_value is not None and delete_success,
                "set_success": set_success
                "get_success": retrieved_value is not None,
                "delete_success": delete_success
                "data_integrity": retrieved_value == test_value if retrieved_value else False
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _test_pattern_operations_async(self) -> Dict[str, Any]:
        """Test pattern-based operations."""
        try:
            # Create test keys
            test_keys = [f"pattern_test_{i}" for i in range(3)]
            for key in test_keys:
                await self.cache_client.set(key, f"value_{key}", ttl=60, namespace="health")

            # Test pattern delete
            deleted_count = await self.cache_client.delete_pattern(
                "pattern_test_*", namespace="health"
            )

            return {
                "success": deleted_count == len(test_keys),
                "deleted_count": deleted_count
                "expected_count": len(test_keys)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_redis_info_async(self) -> Dict[str, Any]:
        """Get Redis server information."""
        try:
            import aioredis
            async with aioredis.Redis(connection_pool=self.cache_client._redis_pool) as redis:
                info = await redis.info()

                # Extract key metrics
                return {
                    "version": info.get("redis_version"),
                    "uptime_seconds": info.get("uptime_in_seconds")
                    "connected_clients": info.get("connected_clients"),
                    "used_memory": info.get("used_memory")
                    "used_memory_human": info.get("used_memory_human"),
                    "total_commands_processed": info.get("total_commands_processed")
                    "keyspace_hits": info.get("keyspace_hits"),
                    "keyspace_misses": info.get("keyspace_misses")
                    "expired_keys": info.get("expired_keys"),
                    "evicted_keys": info.get("evicted_keys")
                }

        except Exception as e:
            return {
                "error": str(e)
            }

    async def _get_connection_pool_stats_async(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        try:
            pool = self.cache_client._redis_pool

            return {
                "max_connections": pool._max_connections if hasattr(pool, '_max_connections') else "unknown",
                "created_connections": pool.created_connections if hasattr(pool, 'created_connections') else "unknown"
                "available_connections": pool.available_connections if hasattr(pool, 'available_connections') else "unknown",
                "in_use_connections": pool.in_use_connections if hasattr(pool, 'in_use_connections') else "unknown"
            }

        except Exception as e:
            return {
                "error": str(e)
            }

    async def get_performance_metrics_async(self) -> PerformanceMetrics:
        """Get current performance metrics.

        Returns:
            PerformanceMetrics object
        """
        try:
            # Get cache client metrics
            client_metrics = self.cache_client.get_metrics()

            # Calculate performance metrics
            total_ops = client_metrics.get("total_operations", 0)
            hits = client_metrics.get("hits", 0)
            errors = client_metrics.get("errors", 0)

            return PerformanceMetrics(
                total_operations=total_ops,
                successful_operations=total_ops - errors
                failed_operations=errors,
                average_response_time_ms=0.0,  # Would need to track this separately
                cache_hit_rate=client_metrics.get("hit_rate_percent", 0.0),
                connection_pool_usage=0.0,  # Would need pool monitoring
                memory_usage_bytes=0  # Would need Redis memory info
            )

        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return PerformanceMetrics()

    def get_health_history(self, limit: int | None = None) -> List[HealthCheckResult]:
        """Get health check history.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of health check results
        """
        if limit is None:
            return self._health_history.copy()
        else:
            return self._health_history[-limit:]

    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of health status.

        Returns:
            Health summary dictionary
        """
        if not self._health_history:
            return {
                "status": "unknown",
                "message": "No health checks performed yet"
            }

        recent_checks = self._health_history[-10:] if len(self._health_history) >= 10 else self._health_history
        healthy_count = sum(1 for check in recent_checks if check.healthy)
        health_rate = (healthy_count / len(recent_checks)) * 100

        latest_check = self._health_history[-1]
        avg_response_time = sum(check.response_time_ms for check in recent_checks) / len(recent_checks)

        status = "healthy"
        if health_rate < 50:
            status = "critical"
        elif health_rate < 80:
            status = "degraded"

        return {
            "status": status,
            "health_rate_percent": round(health_rate, 1)
            "average_response_time_ms": round(avg_response_time, 2),
            "last_check": latest_check.timestamp.isoformat()
            "consecutive_failures": self._consecutive_failures,
            "total_checks": len(self._health_history)
            "monitoring_active": self._monitoring_active
        }

    async def diagnose_issues_async(self) -> Dict[str, Any]:
        """Perform diagnostic analysis of cache issues.

        Returns:
            Diagnostic report
        """
        issues = []
        recommendations = []

        # Analyze health history
        if len(self._health_history) >= 5:
            recent_checks = self._health_history[-5:]
            failed_checks = [check for check in recent_checks if not check.healthy]

            if len(failed_checks) > 2:
                issues.append("High failure rate in recent checks")
                recommendations.append("Check Redis server status and network connectivity")

            # Check response times
            response_times = [check.response_time_ms for check in recent_checks]
            avg_response_time = sum(response_times) / len(response_times)

            if avg_response_time > 500:
                issues.append(f"High average response time: {avg_response_time:.2f}ms")
                recommendations.append("Consider optimizing queries or checking Redis server performance")

        # Check client metrics
        client_metrics = self.cache_client.get_metrics()
        hit_rate = client_metrics.get("hit_rate_percent", 0)

        if hit_rate < 50:
            issues.append(f"Low cache hit rate: {hit_rate:.1f}%")
            recommendations.append("Review caching strategy and TTL values")

        error_count = client_metrics.get("errors", 0)
        if error_count > 10:
            issues.append(f"High error count: {error_count}")
            recommendations.append("Check error logs and Redis connectivity")

        return {
            "issues": issues,
            "recommendations": recommendations
            "client_metrics": client_metrics,
            "health_summary": self.get_health_summary()
        }
