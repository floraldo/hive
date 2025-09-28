"""Load balancer implementation with multiple strategies and circuit breaker."""

import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from .service_registry import ServiceInfo
from .exceptions import LoadBalancerError, ServiceNotFoundError

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    WEIGHTED = "weighted"
    HEALTH_BASED = "health_based"


@dataclass
class ServiceMetrics:
    """Metrics for a service instance."""
    active_connections: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    last_request_time: float = 0.0
    circuit_breaker_open: bool = False
    circuit_breaker_failures: int = 0
    circuit_breaker_last_failure: float = 0.0


class LoadBalancingAlgorithm(ABC):
    """Abstract base class for load balancing algorithms."""

    @abstractmethod
    async def select_service(self, services: List[ServiceInfo], metrics: Dict[str, ServiceMetrics]) -> Optional[ServiceInfo]:
        """Select a service instance based on the algorithm."""
        pass


class RoundRobinAlgorithm(LoadBalancingAlgorithm):
    """Round-robin load balancing algorithm."""

    def __init__(self):
        self._counters: Dict[str, int] = {}

    async def select_service(self, services: List[ServiceInfo], metrics: Dict[str, ServiceMetrics]) -> Optional[ServiceInfo]:
        if not services:
            return None

        # Filter out unhealthy services and those with open circuit breakers
        healthy_services = [
            s for s in services
            if s.healthy and not metrics.get(s.service_id, ServiceMetrics()).circuit_breaker_open
        ]

        if not healthy_services:
            return None

        # Generate unique key for this service group
        service_key = "_".join(sorted(s.service_id for s in healthy_services))

        # Get or initialize counter
        if service_key not in self._counters:
            self._counters[service_key] = 0

        # Select service and increment counter
        selected_index = self._counters[service_key] % len(healthy_services)
        self._counters[service_key] += 1

        return healthy_services[selected_index]


class LeastConnectionsAlgorithm(LoadBalancingAlgorithm):
    """Least connections load balancing algorithm."""

    async def select_service(self, services: List[ServiceInfo], metrics: Dict[str, ServiceMetrics]) -> Optional[ServiceInfo]:
        if not services:
            return None

        # Filter out unhealthy services and those with open circuit breakers
        candidates = [
            s for s in services
            if s.healthy and not metrics.get(s.service_id, ServiceMetrics()).circuit_breaker_open
        ]

        if not candidates:
            return None

        # Select service with least connections
        return min(
            candidates,
            key=lambda s: metrics.get(s.service_id, ServiceMetrics()).active_connections
        )


class RandomAlgorithm(LoadBalancingAlgorithm):
    """Random load balancing algorithm."""

    async def select_service(self, services: List[ServiceInfo], metrics: Dict[str, ServiceMetrics]) -> Optional[ServiceInfo]:
        if not services:
            return None

        # Filter out unhealthy services and those with open circuit breakers
        healthy_services = [
            s for s in services
            if s.healthy and not metrics.get(s.service_id, ServiceMetrics()).circuit_breaker_open
        ]

        if not healthy_services:
            return None

        return random.choice(healthy_services)


class WeightedAlgorithm(LoadBalancingAlgorithm):
    """Weighted load balancing algorithm based on service metadata."""

    async def select_service(self, services: List[ServiceInfo], metrics: Dict[str, ServiceMetrics]) -> Optional[ServiceInfo]:
        if not services:
            return None

        # Filter out unhealthy services and those with open circuit breakers
        candidates = [
            s for s in services
            if s.healthy and not metrics.get(s.service_id, ServiceMetrics()).circuit_breaker_open
        ]

        if not candidates:
            return None

        # Get weights from service metadata (default weight = 1)
        weighted_services = []
        for service in candidates:
            weight = service.metadata.get("weight", 1)
            weighted_services.extend([service] * weight)

        return random.choice(weighted_services) if weighted_services else None


class HealthBasedAlgorithm(LoadBalancingAlgorithm):
    """Health-based load balancing that considers response times and success rates."""

    async def select_service(self, services: List[ServiceInfo], metrics: Dict[str, ServiceMetrics]) -> Optional[ServiceInfo]:
        if not services:
            return None

        # Filter out unhealthy services and those with open circuit breakers
        candidates = [
            s for s in services
            if s.healthy and not metrics.get(s.service_id, ServiceMetrics()).circuit_breaker_open
        ]

        if not candidates:
            return None

        # Calculate health scores for each service
        scored_services = []
        for service in candidates:
            service_metrics = metrics.get(service.service_id, ServiceMetrics())

            # Calculate success rate
            total_requests = service_metrics.total_requests
            success_rate = (
                service_metrics.successful_requests / total_requests
                if total_requests > 0 else 1.0
            )

            # Calculate response time score (lower is better)
            response_time_score = 1.0 / (1.0 + service_metrics.average_response_time)

            # Calculate connection load score (lower is better)
            connection_score = 1.0 / (1.0 + service_metrics.active_connections)

            # Combined health score
            health_score = success_rate * response_time_score * connection_score

            scored_services.append((service, health_score))

        # Select service with highest health score
        return max(scored_services, key=lambda x: x[1])[0]


class LoadBalancer:
    """
    Intelligent load balancer with multiple strategies and circuit breaker.

    Features:
    - Multiple load balancing algorithms
    - Circuit breaker pattern for fault tolerance
    - Service health monitoring
    - Request metrics tracking
    - Sticky sessions support
    - Automatic failover
    """

    def __init__(
        self,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
        enable_sticky_sessions: bool = False
    ):
        self.strategy = strategy
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.enable_sticky_sessions = enable_sticky_sessions

        # Service metrics tracking
        self._service_metrics: Dict[str, ServiceMetrics] = {}

        # Sticky session mapping (session_id -> service_id)
        self._sticky_sessions: Dict[str, str] = {}

        # Load balancing algorithms
        self._algorithms = {
            LoadBalancingStrategy.ROUND_ROBIN: RoundRobinAlgorithm(),
            LoadBalancingStrategy.LEAST_CONNECTIONS: LeastConnectionsAlgorithm(),
            LoadBalancingStrategy.RANDOM: RandomAlgorithm(),
            LoadBalancingStrategy.WEIGHTED: WeightedAlgorithm(),
            LoadBalancingStrategy.HEALTH_BASED: HealthBasedAlgorithm(),
        }

    async def select_service(
        self,
        services: List[ServiceInfo],
        session_id: Optional[str] = None
    ) -> Optional[ServiceInfo]:
        """Select a service instance for load balancing.

        Args:
            services: Available service instances
            session_id: Optional session ID for sticky sessions

        Returns:
            Selected ServiceInfo or None if no healthy service available
        """
        if not services:
            raise ServiceNotFoundError("No services available for load balancing")

        # Handle sticky sessions
        if self.enable_sticky_sessions and session_id:
            if session_id in self._sticky_sessions:
                sticky_service_id = self._sticky_sessions[session_id]
                for service in services:
                    if service.service_id == sticky_service_id and service.healthy:
                        # Check circuit breaker
                        if not self._is_circuit_breaker_open(service.service_id):
                            return service

        # Use load balancing algorithm
        algorithm = self._algorithms[self.strategy]
        selected_service = await algorithm.select_service(services, self._service_metrics)

        if selected_service and self.enable_sticky_sessions and session_id:
            # Create sticky session mapping
            self._sticky_sessions[session_id] = selected_service.service_id

        return selected_service

    async def execute_request(
        self,
        service: ServiceInfo,
        request_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute a request with metrics tracking and circuit breaker.

        Args:
            service: Service to execute request against
            request_func: Async function to execute
            *args: Arguments for request function
            **kwargs: Keyword arguments for request function

        Returns:
            Request result
        """
        service_id = service.service_id

        # Check circuit breaker
        if self._is_circuit_breaker_open(service_id):
            raise LoadBalancerError(
                f"Circuit breaker is open for service {service_id}",
                service_name=service.service_name
            )

        # Initialize metrics if needed
        if service_id not in self._service_metrics:
            self._service_metrics[service_id] = ServiceMetrics()

        metrics = self._service_metrics[service_id]

        # Track active connection
        metrics.active_connections += 1
        metrics.total_requests += 1
        metrics.last_request_time = time.time()

        start_time = time.time()

        try:
            # Execute request
            result = await request_func(*args, **kwargs)

            # Record success
            metrics.successful_requests += 1
            response_time = time.time() - start_time

            # Update average response time (exponential moving average)
            if metrics.average_response_time == 0:
                metrics.average_response_time = response_time
            else:
                metrics.average_response_time = (
                    0.8 * metrics.average_response_time + 0.2 * response_time
                )

            # Reset circuit breaker on success
            metrics.circuit_breaker_failures = 0

            return result

        except Exception as e:
            # Record failure
            metrics.failed_requests += 1
            metrics.circuit_breaker_failures += 1
            metrics.circuit_breaker_last_failure = time.time()

            # Check if circuit breaker should open
            if metrics.circuit_breaker_failures >= self.circuit_breaker_threshold:
                metrics.circuit_breaker_open = True
                logger.warning(
                    f"Circuit breaker opened for service {service_id} "
                    f"after {metrics.circuit_breaker_failures} failures"
                )

            raise LoadBalancerError(
                f"Request failed for service {service_id}: {e}",
                service_name=service.service_name
            ) from e

        finally:
            # Decrement active connections
            metrics.active_connections = max(0, metrics.active_connections - 1)

    def _is_circuit_breaker_open(self, service_id: str) -> bool:
        """Check if circuit breaker is open for a service."""
        if service_id not in self._service_metrics:
            return False

        metrics = self._service_metrics[service_id]

        if not metrics.circuit_breaker_open:
            return False

        # Check if circuit breaker should close (timeout elapsed)
        if time.time() - metrics.circuit_breaker_last_failure > self.circuit_breaker_timeout:
            metrics.circuit_breaker_open = False
            metrics.circuit_breaker_failures = 0
            logger.info(f"Circuit breaker closed for service {service_id}")
            return False

        return True

    async def execute_with_retry(
        self,
        services: List[ServiceInfo],
        request_func: Callable,
        max_retries: int = 3,
        session_id: Optional[str] = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute request with automatic retry and failover.

        Args:
            services: Available service instances
            request_func: Async function to execute
            max_retries: Maximum number of retries
            session_id: Optional session ID for sticky sessions
            *args: Arguments for request function
            **kwargs: Keyword arguments for request function

        Returns:
            Request result
        """
        last_exception = None
        attempted_services = set()

        for attempt in range(max_retries + 1):
            try:
                # Select service (excluding already attempted services if possible)
                available_services = [
                    s for s in services
                    if s.service_id not in attempted_services or len(attempted_services) >= len(services)
                ]

                if not available_services:
                    available_services = services

                selected_service = await self.select_service(available_services, session_id)

                if not selected_service:
                    raise ServiceNotFoundError("No healthy services available")

                attempted_services.add(selected_service.service_id)

                # Execute request
                return await self.execute_request(selected_service, request_func, *args, **kwargs)

            except (LoadBalancerError, ServiceNotFoundError) as e:
                last_exception = e
                if attempt == max_retries:
                    break

                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff

        raise LoadBalancerError(
            f"All retry attempts failed. Last error: {last_exception}",
            details={"attempts": max_retries + 1, "attempted_services": list(attempted_services)}
        )

    def get_service_metrics(self, service_id: str) -> Optional[ServiceMetrics]:
        """Get metrics for a specific service.

        Args:
            service_id: Service ID

        Returns:
            ServiceMetrics or None if not found
        """
        return self._service_metrics.get(service_id)

    def get_all_metrics(self) -> Dict[str, ServiceMetrics]:
        """Get metrics for all services.

        Returns:
            Dictionary of service metrics
        """
        return self._service_metrics.copy()

    def reset_metrics(self, service_id: Optional[str] = None) -> None:
        """Reset metrics for a service or all services.

        Args:
            service_id: Service ID to reset (all if None)
        """
        if service_id:
            if service_id in self._service_metrics:
                self._service_metrics[service_id] = ServiceMetrics()
        else:
            self._service_metrics.clear()

    def force_circuit_breaker_close(self, service_id: str) -> bool:
        """Force close circuit breaker for a service.

        Args:
            service_id: Service ID

        Returns:
            True if circuit breaker was closed
        """
        if service_id in self._service_metrics:
            metrics = self._service_metrics[service_id]
            metrics.circuit_breaker_open = False
            metrics.circuit_breaker_failures = 0
            logger.info(f"Forcibly closed circuit breaker for service {service_id}")
            return True
        return False

    def get_load_balancer_stats(self) -> Dict[str, Any]:
        """Get load balancer statistics.

        Returns:
            Statistics dictionary
        """
        total_requests = sum(m.total_requests for m in self._service_metrics.values())
        total_successful = sum(m.successful_requests for m in self._service_metrics.values())
        total_failed = sum(m.failed_requests for m in self._service_metrics.values())

        success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 0

        open_circuit_breakers = sum(
            1 for m in self._service_metrics.values() if m.circuit_breaker_open
        )

        return {
            "strategy": self.strategy.value,
            "total_requests": total_requests,
            "successful_requests": total_successful,
            "failed_requests": total_failed,
            "success_rate_percent": round(success_rate, 2),
            "active_services": len(self._service_metrics),
            "open_circuit_breakers": open_circuit_breakers,
            "sticky_sessions_enabled": self.enable_sticky_sessions,
            "active_sticky_sessions": len(self._sticky_sessions),
        }