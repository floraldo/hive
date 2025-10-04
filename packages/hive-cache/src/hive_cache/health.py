"""Health monitoring and diagnostics for Hive Cache."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from hive_app_toolkit.api import BaseHealthMonitor, HealthCheckResult
from hive_logging import get_logger

from .cache_client import HiveCacheClient
from .config import CacheConfig

logger = get_logger(__name__)


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


class CacheHealthMonitor(BaseHealthMonitor):
    """
    Redis cache health monitoring implementation.

    Extends BaseHealthMonitor with Redis-specific checks:
    - Redis ping connectivity
    - Set/get/delete operations
    - Pattern-based operations
    - Redis server info
    - Connection pool statistics
    """

    def __init__(self, cache_client: HiveCacheClient, config: CacheConfig) -> None:
        """
        Initialize cache health monitor.

        Args:
            cache_client: HiveCacheClient instance to monitor
            config: Cache configuration
        """
        # Initialize base class
        super().__init__(
            check_interval=config.health_check_interval,
            max_history_size=100,
            alert_thresholds={
                "response_time_ms": 1000,
                "error_rate_percent": 10,
                "consecutive_failures": 3,
            },
        )

        # Redis-specific attributes
        self.cache_client = cache_client
        self.config = config

    async def _perform_component_health_check_async(self) -> HealthCheckResult:
        """
        Perform Redis-specific health checks.

        Executes multiple Redis operations to verify cache health:
        - Ping connectivity
        - Set/get/delete operations
        - Pattern-based operations
        - Server info retrieval
        - Connection pool status

        Returns:
            HealthCheckResult with Redis-specific details
        """
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

            # Determine overall health
            healthy = all(
                [
                    ping_result.get("success", False),
                    set_get_result.get("success", False),
                    pattern_result.get("success", False),
                ]
            )

            return HealthCheckResult(
                healthy=healthy,
                timestamp=datetime.utcnow(),
                response_time_ms=0,  # Base class will set this
                details=details,
                errors=errors,
            )

        except Exception as e:
            errors.append(str(e))
            logger.error(f"Redis health check failed: {e}")

            return HealthCheckResult(
                healthy=False,
                timestamp=datetime.utcnow(),
                response_time_ms=0,  # Base class will set this
                details=details,
                errors=errors,
            )

    async def _test_ping_async(self) -> dict[str, Any]:
        """Test Redis ping operation."""
        try:
            import aioredis
            async with aioredis.Redis(connection_pool=self.cache_client._redis_pool) as redis:
                start_time = time.time()
                result = await redis.ping()
                ping_time = (time.time() - start_time) * 1000

                return {
                    "success": True,
                    "result": result,
                    "ping_time_ms": ping_time,
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _test_set_get_async(self) -> dict[str, Any]:
        """Test set/get operations."""
        try:
            test_key = f"health_check_{int(time.time())}"
            test_value = {"test": True, "timestamp": time.time()}

            # Test set,
            set_success = await self.cache_client.set(
                test_key, test_value, ttl=60, namespace="health"
            )

            # Test get,
            retrieved_value = await self.cache_client.get(test_key, namespace="health")

            # Test delete,
            delete_success = await self.cache_client.delete(test_key, namespace="health")

            return {
                "success": set_success and retrieved_value is not None and delete_success,
                "set_success": set_success,
                "get_success": retrieved_value is not None,
                "delete_success": delete_success,
                "data_integrity": retrieved_value == test_value if retrieved_value else False,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _test_pattern_operations_async(self) -> dict[str, Any]:
        """Test pattern-based operations."""
        try:
            # Create test keys,
            test_keys = [f"pattern_test_{i}" for i in range(3)]
            for key in test_keys:
                await self.cache_client.set(key, f"value_{key}", ttl=60, namespace="health")

            # Test pattern delete,
            deleted_count = await self.cache_client.delete_pattern(
                "pattern_test_*", namespace="health"
            )

            return {
                "success": deleted_count == len(test_keys),
                "deleted_count": deleted_count,
                "expected_count": len(test_keys)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_redis_info_async(self) -> dict[str, Any]:
        """Get Redis server information."""
        try:
            import aioredis
            async with aioredis.Redis(connection_pool=self.cache_client._redis_pool) as redis:
                info = await redis.info()

                # Extract key metrics,
                return {
                    "version": info.get("redis_version"),
                    "uptime_seconds": info.get("uptime_in_seconds"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory": info.get("used_memory"),
                    "used_memory_human": info.get("used_memory_human"),
                    "total_commands_processed": info.get("total_commands_processed"),
                    "keyspace_hits": info.get("keyspace_hits"),
                    "keyspace_misses": info.get("keyspace_misses"),
                    "expired_keys": info.get("expired_keys"),
                    "evicted_keys": info.get("evicted_keys")
                }

        except Exception as e:
            return {
                "error": str(e)
            }

    async def _get_connection_pool_stats_async(self) -> dict[str, Any]:
        """Get connection pool statistics."""
        try:
            pool = self.cache_client._redis_pool

            return {
                "max_connections": pool._max_connections if hasattr(pool, '_max_connections') else "unknown",
                "created_connections": pool.created_connections if hasattr(pool, 'created_connections') else "unknown",
                "available_connections": pool.available_connections if hasattr(pool, 'available_connections') else "unknown",
                "in_use_connections": pool.in_use_connections if hasattr(pool, 'in_use_connections') else "unknown",
            }

        except Exception as e:
            return {
                "error": str(e)
            }

    async def get_performance_metrics_async(self) -> PerformanceMetrics:
        """Get current performance metrics.

        Returns:
            PerformanceMetrics object,
        """
        try:
            # Get cache client metrics,
            client_metrics = self.cache_client.get_metrics()

            # Calculate performance metrics,
            total_ops = client_metrics.get("total_operations", 0)
            client_metrics.get("hits", 0)
            errors = client_metrics.get("errors", 0)

            return PerformanceMetrics(
                total_operations=total_ops,
                successful_operations=total_ops - errors,
                failed_operations=errors,
                average_response_time_ms=0.0,  # Would need to track this separately,
                cache_hit_rate=client_metrics.get("hit_rate_percent", 0.0),
                connection_pool_usage=0.0,  # Would need pool monitoring,
                memory_usage_bytes=0  # Would need Redis memory info
            )

        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return PerformanceMetrics()

    async def diagnose_issues_async(self) -> dict[str, Any]:
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
            "recommendations": recommendations,
            "client_metrics": client_metrics,
            "health_summary": self.get_health_summary()
        }
