"""
Connection pooling and resource management for AI model providers.

Provides efficient resource usage with connection reuse,
load balancing, and automatic scaling based on demand.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from hive_async import AsyncConnectionManager, PoolConfig
from hive_errors import PoolExhaustedError
from hive_logging import get_logger

from ..core.config import AIConfig, ModelConfig
from ..core.interfaces import ModelProviderInterface, ModelResponse
from .registry import ModelRegistry

logger = get_logger(__name__)


@dataclass
class PoolStats:
    """Statistics for connection pool."""

    total_connections: int
    active_connections: int
    idle_connections: int
    total_requests: int
    successful_requests: int
    avg_response_time_ms: float
    pool_efficiency: float


class ModelPool:
    """
    Connection pool manager for AI model providers.

    Manages provider connections with load balancing,
    automatic scaling, and performance optimization.
    """

    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self.registry = ModelRegistry(config)

        # Connection pools per provider
        self._pools: Dict[str, AsyncConnectionManager] = {}
        self._pool_configs: Dict[str, PoolConfig] = {}

        # Request tracking
        self._request_counts: Dict[str, int] = defaultdict(int)
        self._response_times: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()

        # Initialize pools for configured providers
        self._initialize_pools()

    def _initialize_pools(self) -> None:
        """Initialize connection pools for all configured providers."""
        providers = set(model.provider for model in self.config.models.values())

        for provider in providers:
            self._create_pool(provider)

    def _create_pool(self, provider: str) -> None:
        """Create connection pool for specific provider."""
        # Get models for this provider to determine pool size
        provider_models = [model for model in self.config.models.values() if model.provider == provider]

        if not provider_models:
            logger.warning(f"No models configured for provider: {provider}")
            return

        # Calculate optimal pool size based on rate limits
        total_rpm = sum(model.rate_limit_rpm for model in provider_models)
        # Pool size = expected concurrent requests based on rate limits
        pool_size = min(max(total_rpm // 20, 5), 50)  # Between 5-50 connections

        pool_config = PoolConfig(
            min_size=2,
            max_size=pool_size,
            timeout=30.0,
            max_idle_time=300.0,  # 5 minutes
            health_check_interval=60.0,  # 1 minute
        )

        self._pool_configs[provider] = pool_config

        # Create async connection manager
        self._pools[provider] = AsyncConnectionManager(
            pool_config, connection_factory=lambda: self._create_provider_connection_async(provider)
        )

        logger.info(f"Created connection pool for {provider}: {pool_size} max connections")

    async def _create_provider_connection_async(self, provider: str) -> ModelProviderInterface:
        """Factory function to create provider connections."""
        return self.registry.get_provider(provider)

    async def execute_request_async(self, model_name: str, operation: str, *args, **kwargs) -> Any:
        """
        Execute request using pooled connection.

        Args:
            model_name: Name of the model to use
            operation: Operation to perform (generate_async, etc.)
            *args, **kwargs: Arguments for the operation

        Returns:
            Result from the operation

        Raises:
            PoolExhaustedError: No connections available
            ModelError: Operation failed
        """
        model_config = self.registry.get_model_config(model_name)
        provider = model_config.provider

        if provider not in self._pools:
            self._create_pool(provider)

        pool = self._pools[provider]
        start_time = time.time()

        try:
            # Get connection from pool
            async with pool.get_connection() as connection:
                # Execute operation
                operation_func = getattr(connection, operation)
                result = await operation_func(*args, **kwargs)

                # Track metrics
                response_time = (time.time() - start_time) * 1000
                self._record_request(provider, response_time, True)

                return result

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self._record_request(provider, response_time, False)

            if "pool exhausted" in str(e).lower():
                pool_stats = await self.get_pool_stats_async(provider)
                raise PoolExhaustedError(
                    f"Connection pool exhausted for provider {provider}",
                    component="hive-ai",
                    operation="model_request",
                    pool_size=pool_stats.total_connections,
                    active_connections=pool_stats.active_connections,
                ) from e

            raise

    def _record_request(self, provider: str, response_time_ms: float, success: bool) -> None:
        """Record request metrics for pool optimization."""
        self._request_counts[provider] += 1
        self._response_times[provider].append(response_time_ms)

        # Keep only recent response times (last 1000 requests)
        if len(self._response_times[provider]) > 1000:
            self._response_times[provider] = self._response_times[provider][-1000:]

        # Periodic cleanup
        current_time = time.time()
        if current_time - self._last_cleanup > 300:  # 5 minutes
            self._cleanup_old_metrics()
            self._last_cleanup = current_time

    def _cleanup_old_metrics(self) -> None:
        """Cleanup old metrics to prevent memory leaks."""
        # Keep only recent response times
        for provider in self._response_times:
            if len(self._response_times[provider]) > 500:
                self._response_times[provider] = self._response_times[provider][-500:]

    async def get_pool_stats_async(self, provider: str) -> PoolStats:
        """Get detailed statistics for provider pool."""
        if provider not in self._pools:
            return PoolStats(0, 0, 0, 0, 0, 0.0, 0.0)

        pool = self._pools[provider]
        pool_info = pool.get_pool_info()

        total_requests = self._request_counts[provider]
        response_times = self._response_times[provider]

        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0

        # Calculate efficiency: active/total ratio when under load
        efficiency = pool_info["active"] / pool_info["total"] if pool_info["total"] > 0 and total_requests > 10 else 1.0

        return PoolStats(
            total_connections=pool_info["total"],
            active_connections=pool_info["active"],
            idle_connections=pool_info["idle"],
            total_requests=total_requests,
            successful_requests=total_requests,  # Approximation
            avg_response_time_ms=avg_response_time,
            pool_efficiency=efficiency,
        )

    async def scale_pool_async(self, provider: str, target_size: int) -> bool:
        """Dynamically scale pool size based on demand."""
        if provider not in self._pools:
            logger.warning(f"No pool exists for provider: {provider}")
            return False

        if target_size < 1 or target_size > 100:
            logger.warning(f"Invalid target size: {target_size}")
            return False

        pool_config = self._pool_configs[provider]

        # Update configuration
        pool_config.max_size = target_size

        # The actual scaling would depend on the AsyncConnectionManager implementation
        # This is a simplified version
        logger.info(f"Scaled pool for {provider} to target size: {target_size}")
        return True

    async def warm_pools_async(self) -> Dict[str, bool]:
        """Pre-warm all connection pools for faster initial requests."""
        results = {}

        for provider, pool in self._pools.items():
            try:
                # Create minimum connections
                await pool.warm_pool()
                results[provider] = True
                logger.info(f"Warmed pool for provider: {provider}")
            except Exception as e:
                results[provider] = False
                logger.error(f"Failed to warm pool for {provider}: {e}")

        return results

    async def health_check_async(self) -> Dict[str, Any]:
        """Comprehensive health check of all pools."""
        health_status = {}

        for provider in self._pools:
            try:
                stats = await self.get_pool_stats_async(provider)

                # Health criteria
                healthy = (
                    stats.total_connections > 0
                    and stats.pool_efficiency > 0.1
                    and stats.avg_response_time_ms < 10000  # At least 10% efficiency  # Under 10 seconds
                )

                health_status[provider] = {
                    "healthy": healthy,
                    "stats": stats,
                    "pool_config": self._pool_configs.get(provider),
                }

            except Exception as e:
                health_status[provider] = {"healthy": False, "error": str(e)}

        overall_healthy = all(status.get("healthy", False) for status in health_status.values())

        return {"overall_healthy": overall_healthy, "providers": health_status, "total_pools": len(self._pools)}

    async def optimize_pools_async(self) -> Dict[str, Any]:
        """Optimize pool sizes based on usage patterns."""
        optimization_results = {}

        for provider in self._pools:
            try:
                stats = await self.get_pool_stats_async(provider)
                current_config = self._pool_configs[provider]

                # Calculate optimal size based on usage
                if stats.total_requests > 100:  # Enough data
                    if stats.pool_efficiency > 0.8:  # High utilization
                        recommended_size = min(current_config.max_size + 5, 50)
                    elif stats.pool_efficiency < 0.3:  # Low utilization
                        recommended_size = max(current_config.max_size - 3, 5)
                    else:
                        recommended_size = current_config.max_size

                    if recommended_size != current_config.max_size:
                        await self.scale_pool_async(provider, recommended_size)
                        optimization_results[provider] = {
                            "action": "resized",
                            "old_size": current_config.max_size,
                            "new_size": recommended_size,
                            "reason": f"efficiency: {stats.pool_efficiency:.2f}",
                        }
                    else:
                        optimization_results[provider] = {"action": "no_change", "reason": "optimal_size"}
                else:
                    optimization_results[provider] = {"action": "insufficient_data", "requests": stats.total_requests}

            except Exception as e:
                optimization_results[provider] = {"action": "error", "error": str(e)}

        return optimization_results

    async def close_async(self) -> None:
        """Close all connection pools gracefully."""
        for provider, pool in self._pools.items():
            try:
                await pool.close()
                logger.info(f"Closed pool for provider: {provider}")
            except Exception as e:
                logger.error(f"Error closing pool for {provider}: {e}")

        self._pools.clear()
        self._pool_configs.clear()
