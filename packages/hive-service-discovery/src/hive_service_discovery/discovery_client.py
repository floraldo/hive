"""Service discovery client for finding and connecting to services."""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
import time

from .service_registry import ServiceRegistry, ServiceInfo
from .load_balancer import LoadBalancer, LoadBalancingStrategy
from .health_monitor import HealthMonitor
from .config import ServiceDiscoveryConfig
from .exceptions import ServiceNotFoundError, ServiceDiscoveryError

logger = logging.getLogger(__name__)


class DiscoveryClient:
    """
    Service discovery client for finding and connecting to services.

    Features:
    - Service discovery with caching
    - Integrated load balancing
    - Health monitoring
    - Automatic service updates
    - Connection pooling support
    - Event-driven service changes
    """

    def __init__(self, config: ServiceDiscoveryConfig):
        self.config = config
        self.registry = ServiceRegistry(config)
        self.load_balancer = LoadBalancer(
            strategy=LoadBalancingStrategy(config.load_balancer.strategy),
            circuit_breaker_threshold=config.load_balancer.circuit_breaker_threshold,
            circuit_breaker_timeout=config.load_balancer.circuit_breaker_timeout,
            enable_sticky_sessions=config.load_balancer.enable_sticky_sessions
        )
        self.health_monitor = HealthMonitor(config)

        # Service cache
        self._service_cache: Dict[str, List[ServiceInfo]] = {}
        self._cache_timestamps: Dict[str, float] = {}

        # Background tasks
        self._discovery_task = None
        self._running = False

        # Event callbacks
        self._service_added_callbacks: List[Callable] = []
        self._service_removed_callbacks: List[Callable] = []
        self._service_health_changed_callbacks: List[Callable] = []

    async def initialize(self) -> None:
        """Initialize the discovery client."""
        try:
            # Initialize components
            await self.registry.initialize()
            await self.health_monitor.initialize()

            self._running = True

            # Start background discovery task
            self._discovery_task = asyncio.create_task(self._discovery_loop())

            logger.info("Service discovery client initialized")

        except Exception as e:
            logger.error(f"Failed to initialize discovery client: {e}")
            raise ServiceDiscoveryError(f"Discovery client initialization failed: {e}")

    async def shutdown(self) -> None:
        """Shutdown the discovery client."""
        self._running = False

        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass

        await self.health_monitor.shutdown()
        await self.registry.shutdown()

        logger.info("Service discovery client shut down")

    async def _discovery_loop(self) -> None:
        """Background loop for service discovery updates."""
        while self._running:
            try:
                # Refresh service cache
                await self._refresh_all_services()

                # Update health monitoring
                await self._update_health_monitoring()

                await asyncio.sleep(self.config.discovery_interval)

            except Exception as e:
                logger.error(f"Error in discovery loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _refresh_all_services(self) -> None:
        """Refresh cache for all known services."""
        try:
            # Get all service names
            service_names = await self.registry.get_service_names()

            # Refresh cache for each service
            for service_name in service_names:
                await self._refresh_service_cache(service_name)

        except Exception as e:
            logger.error(f"Failed to refresh service cache: {e}")

    async def _refresh_service_cache(self, service_name: str) -> None:
        """Refresh cache for a specific service."""
        try:
            # Get fresh service list
            services = await self.registry.get_services_by_name(service_name, healthy_only=False)

            # Compare with cached services
            cached_services = self._service_cache.get(service_name, [])
            cached_ids = {s.service_id for s in cached_services}
            current_ids = {s.service_id for s in services}

            # Detect added services
            added_ids = current_ids - cached_ids
            for service in services:
                if service.service_id in added_ids:
                    await self._notify_service_added(service)

            # Detect removed services
            removed_ids = cached_ids - current_ids
            for cached_service in cached_services:
                if cached_service.service_id in removed_ids:
                    await self._notify_service_removed(cached_service)

            # Update cache
            self._service_cache[service_name] = services
            self._cache_timestamps[service_name] = time.time()

        except Exception as e:
            logger.error(f"Failed to refresh cache for {service_name}: {e}")

    async def _update_health_monitoring(self) -> None:
        """Update health monitoring for all services."""
        try:
            all_services = []
            for services in self._service_cache.values():
                all_services.extend(services)

            # Update health monitoring
            await self.health_monitor.update_services(all_services)

        except Exception as e:
            logger.error(f"Failed to update health monitoring: {e}")

    async def discover_service(
        self,
        service_name: str,
        refresh_cache: bool = False
    ) -> List[ServiceInfo]:
        """Discover instances of a service.

        Args:
            service_name: Name of the service to discover
            refresh_cache: Force refresh of service cache

        Returns:
            List of service instances
        """
        try:
            # Check if cache refresh is needed
            if refresh_cache or self._is_cache_stale(service_name):
                await self._refresh_service_cache(service_name)

            # Return cached services
            return self._service_cache.get(service_name, [])

        except Exception as e:
            logger.error(f"Failed to discover service {service_name}: {e}")
            raise ServiceNotFoundError(f"Service discovery failed: {e}", service_name=service_name)

    async def get_healthy_services(self, service_name: str) -> List[ServiceInfo]:
        """Get only healthy instances of a service.

        Args:
            service_name: Name of the service

        Returns:
            List of healthy service instances
        """
        services = await self.discover_service(service_name)
        return [s for s in services if s.healthy]

    async def select_service_instance(
        self,
        service_name: str,
        session_id: Optional[str] = None
    ) -> Optional[ServiceInfo]:
        """Select a service instance using load balancing.

        Args:
            service_name: Name of the service
            session_id: Optional session ID for sticky sessions

        Returns:
            Selected service instance or None
        """
        try:
            healthy_services = await self.get_healthy_services(service_name)

            if not healthy_services:
                raise ServiceNotFoundError(f"No healthy instances found for service {service_name}")

            return await self.load_balancer.select_service(healthy_services, session_id)

        except Exception as e:
            logger.error(f"Failed to select service instance for {service_name}: {e}")
            raise

    async def execute_service_request(
        self,
        service_name: str,
        request_func: Callable,
        max_retries: int = None,
        session_id: Optional[str] = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute a request against a service with load balancing and retry.

        Args:
            service_name: Name of the service
            request_func: Async function to execute
            max_retries: Maximum retries (uses config default if None)
            session_id: Optional session ID for sticky sessions
            *args: Arguments for request function
            **kwargs: Keyword arguments for request function

        Returns:
            Request result
        """
        if max_retries is None:
            max_retries = self.config.load_balancer.max_retries

        try:
            healthy_services = await self.get_healthy_services(service_name)

            if not healthy_services:
                raise ServiceNotFoundError(f"No healthy instances found for service {service_name}")

            return await self.load_balancer.execute_with_retry(
                healthy_services,
                request_func,
                max_retries,
                session_id,
                *args,
                **kwargs
            )

        except Exception as e:
            logger.error(f"Service request failed for {service_name}: {e}")
            raise

    async def get_service_address(self, service_name: str) -> Optional[str]:
        """Get address of a service instance.

        Args:
            service_name: Name of the service

        Returns:
            Service address in format "host:port" or None
        """
        service = await self.select_service_instance(service_name)
        return service.get_address() if service else None

    def _is_cache_stale(self, service_name: str) -> bool:
        """Check if service cache is stale."""
        if service_name not in self._cache_timestamps:
            return True

        cache_age = time.time() - self._cache_timestamps[service_name]
        return cache_age > self.config.cache_ttl

    # Event handling methods

    def on_service_added(self, callback: Callable[[ServiceInfo], None]) -> None:
        """Register callback for service added events.

        Args:
            callback: Function to call when service is added
        """
        self._service_added_callbacks.append(callback)

    def on_service_removed(self, callback: Callable[[ServiceInfo], None]) -> None:
        """Register callback for service removed events.

        Args:
            callback: Function to call when service is removed
        """
        self._service_removed_callbacks.append(callback)

    def on_service_health_changed(self, callback: Callable[[ServiceInfo, bool], None]) -> None:
        """Register callback for service health change events.

        Args:
            callback: Function to call when service health changes
        """
        self._service_health_changed_callbacks.append(callback)

    async def _notify_service_added(self, service: ServiceInfo) -> None:
        """Notify listeners of service addition."""
        for callback in self._service_added_callbacks:
            try:
                await callback(service) if asyncio.iscoroutinefunction(callback) else callback(service)
            except Exception as e:
                logger.error(f"Error in service added callback: {e}")

    async def _notify_service_removed(self, service: ServiceInfo) -> None:
        """Notify listeners of service removal."""
        for callback in self._service_removed_callbacks:
            try:
                await callback(service) if asyncio.iscoroutinefunction(callback) else callback(service)
            except Exception as e:
                logger.error(f"Error in service removed callback: {e}")

    async def _notify_service_health_changed(self, service: ServiceInfo, healthy: bool) -> None:
        """Notify listeners of service health change."""
        for callback in self._service_health_changed_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(service, healthy)
                else:
                    callback(service, healthy)
            except Exception as e:
                logger.error(f"Error in service health changed callback: {e}")

    # Utility methods

    async def get_all_services(self) -> Dict[str, List[ServiceInfo]]:
        """Get all discovered services.

        Returns:
            Dictionary mapping service names to service instances
        """
        return self._service_cache.copy()

    async def get_service_count(self, service_name: str) -> int:
        """Get count of service instances.

        Args:
            service_name: Name of the service

        Returns:
            Number of service instances
        """
        services = await self.discover_service(service_name)
        return len(services)

    async def get_healthy_service_count(self, service_name: str) -> int:
        """Get count of healthy service instances.

        Args:
            service_name: Name of the service

        Returns:
            Number of healthy service instances
        """
        healthy_services = await self.get_healthy_services(service_name)
        return len(healthy_services)

    def get_discovery_stats(self) -> Dict[str, Any]:
        """Get discovery client statistics.

        Returns:
            Statistics dictionary
        """
        total_services = sum(len(services) for services in self._service_cache.values())
        healthy_services = sum(
            len([s for s in services if s.healthy])
            for services in self._service_cache.values()
        )

        return {
            "total_service_names": len(self._service_cache),
            "total_service_instances": total_services,
            "healthy_service_instances": healthy_services,
            "unhealthy_service_instances": total_services - healthy_services,
            "cache_entries": len(self._cache_timestamps),
            "load_balancer_stats": self.load_balancer.get_load_balancer_stats(),
            "health_monitor_stats": self.health_monitor.get_monitor_stats(),
        }

    async def clear_cache(self, service_name: Optional[str] = None) -> None:
        """Clear service cache.

        Args:
            service_name: Service to clear (all if None)
        """
        if service_name:
            self._service_cache.pop(service_name, None)
            self._cache_timestamps.pop(service_name, None)
        else:
            self._service_cache.clear()
            self._cache_timestamps.clear()

        logger.info(f"Cleared service cache for: {service_name or 'all services'}")

    async def force_refresh(self, service_name: Optional[str] = None) -> None:
        """Force refresh of service cache.

        Args:
            service_name: Service to refresh (all if None)
        """
        if service_name:
            await self._refresh_service_cache(service_name)
        else:
            await self._refresh_all_services()

        logger.info(f"Forced refresh for: {service_name or 'all services'}")