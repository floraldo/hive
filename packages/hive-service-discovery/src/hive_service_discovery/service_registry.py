"""Service registry implementation for managing service instances.

# golden-rule-ignore: package-app-discipline - This is infrastructure registry, not business logic
"""
from __future__ import annotations


import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set

import aioredis
from hive_logging import get_logger
from pydantic import BaseModel

from .config import ServiceDiscoveryConfig
from .exceptions import ServiceNotFoundError, ServiceRegistrationError

logger = get_logger(__name__)


@dataclass
class ServiceInfo:
    """Information about a registered service instance."""

    service_id: str
    service_name: str
    host: str
    port: int
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    health_check_url: str | None = None
    ttl: int = 60
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    healthy: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "host": self.host,
            "port": self.port,
            "tags": self.tags,
            "metadata": self.metadata,
            "health_check_url": self.health_check_url,
            "ttl": self.ttl,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "healthy": self.healthy,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceInfo":
        """Create from dictionary."""
        return cls(
            service_id=data["service_id"],
            service_name=data["service_name"],
            host=data["host"],
            port=data["port"],
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            health_check_url=data.get("health_check_url"),
            ttl=data.get("ttl", 60),
            registered_at=datetime.fromisoformat(data.get("registered_at", datetime.utcnow().isoformat())),
            last_heartbeat=datetime.fromisoformat(data.get("last_heartbeat", datetime.utcnow().isoformat())),
            healthy=data.get("healthy", True),
        )

    def get_address(self) -> str:
        """Get full service address."""
        return f"{self.host}:{self.port}"

    def is_expired(self) -> bool:
        """Check if service registration has expired."""
        return (datetime.utcnow() - self.last_heartbeat).total_seconds() > self.ttl


class ServiceRegistry:
    """
    Service registry for managing service instances with Redis backend.

    Features:
    - Service registration and deregistration
    - Automatic TTL management with heartbeats
    - Service discovery with filtering
    - Health status tracking
    - Event notifications for service changes
    """

    def __init__(self, config: ServiceDiscoveryConfig) -> None:
        self.config = config
        self._redis = None
        self._running = False
        self._cleanup_task = None

        # Service registry keys
        self._service_key_prefix = "hive:services"
        self._service_list_key = f"{self._service_key_prefix}:list"
        self._heartbeat_key_prefix = f"{self._service_key_prefix}:heartbeat_async"

        # Local cache
        self._service_cache: Dict[str, ServiceInfo] = {}
        self._cache_last_updated = 0

    async def initialize_async(self) -> None:
        """Initialize the service registry."""
        try:
            # Connect to Redis
            self._redis = aioredis.from_url(self.config.registry_url, encoding="utf-8", decode_responses=True)

            # Test connection
            await self._redis.ping()

            self._running = True

            # Start cleanup task
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_services_async())

            logger.info("Service registry initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize_async service registry: {e}")
            raise ServiceRegistrationError(f"Registry initialization failed: {e}")

    async def shutdown_async(self) -> None:
        """Shutdown the service registry."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._redis:
            await self._redis.close()

        logger.info("Service registry shut down")

    async def register_service_async(
        self,
        service_name: str,
        host: str,
        port: int,
        service_id: str | None = None,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
        health_check_url: str | None = None,
        ttl: int | None = None,
    ) -> str:
        """Register a service instance.

        Args:
            service_name: Name of the service
            host: Service host address
            port: Service port
            service_id: Optional service ID (auto-generated if None)
            tags: Service tags for filtering
            metadata: Additional service metadata
            health_check_url: Health check endpoint URL
            ttl: Time to live for registration

        Returns:
            Service ID
        """
        if service_id is None:
            service_id = f"{service_name}-{uuid.uuid4().hex[:8]}"

        if ttl is None:
            ttl = self.config.service_ttl

        # Create service info
        service_info = ServiceInfo(
            service_id=service_id,
            service_name=service_name,
            host=host,
            port=port,
            tags=tags or [],
            metadata=metadata or {},
            health_check_url=health_check_url,
            ttl=ttl,
        )

        try:
            # Store service information
            service_key = f"{self._service_key_prefix}:{service_id}"
            await self._redis.setex(service_key, ttl, json.dumps(service_info.to_dict()))

            # Add to service list
            await self._redis.sadd(self._service_list_key, service_id)

            # Set heartbeat_async
            await self._set_heartbeat_async(service_id)

            # Update local cache
            self._service_cache[service_id] = service_info

            logger.info(f"Registered service: {service_name} ({service_id}) at {host}:{port}")
            return service_id

        except Exception as e:
            logger.error(f"Failed to register service {service_name}: {e}")
            raise ServiceRegistrationError(f"Service registration failed: {e}", service_name=service_name)

    async def deregister_service_async(self, service_id: str) -> bool:
        """Deregister a service instance.

        Args:
            service_id: Service ID to deregister

        Returns:
            True if service was deregistered
        """
        try:
            # Remove from Redis
            service_key = f"{self._service_key_prefix}:{service_id}"
            heartbeat_key = f"{self._heartbeat_key_prefix}:{service_id}"

            # Use pipeline for atomic operations
            async with self._redis.pipeline() as pipe:
                pipe.delete(service_key)
                pipe.delete(heartbeat_key)
                pipe.srem(self._service_list_key, service_id)
                await pipe.execute()

            # Remove from local cache
            self._service_cache.pop(service_id, None)

            logger.info(f"Deregistered service: {service_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to deregister service {service_id}: {e}")
            return False

    async def heartbeat_async(self, service_id: str) -> bool:
        """Send heartbeat_async for a service instance.

        Args:
            service_id: Service ID

        Returns:
            True if heartbeat_async was recorded
        """
        try:
            # Check if service exists
            service_key = f"{self._service_key_prefix}:{service_id}"
            if not await self._redis.exists(service_key):
                return False

            # Update heartbeat_async
            await self._set_heartbeat_async(service_id)

            # Update cache if present
            if service_id in self._service_cache:
                self._service_cache[service_id].last_heartbeat = datetime.utcnow()

            return True

        except Exception as e:
            logger.error(f"Failed to record heartbeat_async for {service_id}: {e}")
            return False

    async def _set_heartbeat_async(self, service_id: str) -> None:
        """Set heartbeat_async timestamp for a service."""
        heartbeat_key = f"{self._heartbeat_key_prefix}:{service_id}"
        await self._redis.setex(heartbeat_key, self.config.service_ttl, time.time())

    async def get_service_async(self, service_id: str) -> ServiceInfo | None:
        """Get service information by ID.

        Args:
            service_id: Service ID

        Returns:
            ServiceInfo or None if not found
        """
        try:
            # Check cache first
            if service_id in self._service_cache:
                service = self._service_cache[service_id]
                if not service.is_expired():
                    return service

            # Fetch from Redis
            service_key = f"{self._service_key_prefix}:{service_id}"
            data = await self._redis.get(service_key)

            if data:
                service_info = ServiceInfo.from_dict(json.loads(data))
                self._service_cache[service_id] = service_info
                return service_info

            return None

        except Exception as e:
            logger.error(f"Failed to get service {service_id}: {e}")
            return None

    async def get_services_by_name_async(self, service_name: str, healthy_only: bool = True) -> List[ServiceInfo]:
        """Get all instances of a service by name.

        Args:
            service_name: Service name to search for
            healthy_only: Return only healthy services

        Returns:
            List of ServiceInfo instances
        """
        try:
            # Refresh cache if needed
            await self._refresh_cache_if_needed_async()

            services = []
            for service in self._service_cache.values():
                if service.service_name == service_name:
                    if not healthy_only or service.healthy:
                        services.append(service)

            return services

        except Exception as e:
            logger.error(f"Failed to get services for {service_name}: {e}")
            return []

    async def get_services_by_tags_async(self, tags: List[str], match_all: bool = True) -> List[ServiceInfo]:
        """Get services by tags.

        Args:
            tags: Tags to filter by
            match_all: If True, service must have all tags; if False, any tag

        Returns:
            List of ServiceInfo instances
        """
        try:
            await self._refresh_cache_if_needed_async()

            services = []
            for service in self._service_cache.values():
                if match_all:
                    if all(tag in service.tags for tag in tags):
                        services.append(service)
                else:
                    if any(tag in service.tags for tag in tags):
                        services.append(service)

            return services

        except Exception as e:
            logger.error(f"Failed to get services by tags {tags}: {e}")
            return []

    async def get_all_services_async(self) -> List[ServiceInfo]:
        """Get all registered services.

        Returns:
            List of all ServiceInfo instances
        """
        try:
            await self._refresh_cache_if_needed_async()
            return list(self._service_cache.values())

        except Exception as e:
            logger.error(f"Failed to get all services: {e}")
            return []

    async def get_service_names_async(self) -> Set[str]:
        """Get all unique service names.

        Returns:
            Set of service names
        """
        try:
            await self._refresh_cache_if_needed_async()
            return {service.service_name for service in self._service_cache.values()}

        except Exception as e:
            logger.error(f"Failed to get service names: {e}")
            return set()

    async def update_service_health_async(self, service_id: str, healthy: bool) -> bool:
        """Update health status of a service.

        Args:
            service_id: Service ID
            healthy: Health status

        Returns:
            True if health status was updated
        """
        try:
            service = await self.get_service_async(service_id)
            if not service:
                return False

            # Update health status
            service.healthy = healthy

            # Store updated service info
            service_key = f"{self._service_key_prefix}:{service_id}"
            await self._redis.setex(service_key, service.ttl, json.dumps(service.to_dict()))

            # Update cache
            self._service_cache[service_id] = service

            logger.info(f"Updated health status for {service_id}: {healthy}")
            return True

        except Exception as e:
            logger.error(f"Failed to update health for {service_id}: {e}")
            return False

    async def _refresh_cache_if_needed_async(self) -> None:
        """Refresh service cache if it's stale."""
        current_time = time.time()
        if current_time - self._cache_last_updated > self.config.cache_ttl:
            await self._refresh_cache_async()

    async def _refresh_cache_async(self) -> None:
        """Refresh the service cache from Redis."""
        try:
            # Get all service IDs
            service_ids = await self._redis.smembers(self._service_list_key)

            # Fetch all service data
            if service_ids:
                service_keys = [f"{self._service_key_prefix}:{service_id}" for service_id in service_ids]
                service_data = await self._redis.mget(service_keys)

                # Update cache
                new_cache = {}
                for service_id, data in zip(service_ids, service_data):
                    if data:
                        try:
                            service_info = ServiceInfo.from_dict(json.loads(data))
                            new_cache[service_id] = service_info
                        except Exception as e:
                            logger.warning(f"Failed to parse service data for {service_id}: {e}")

                self._service_cache = new_cache

            self._cache_last_updated = time.time()

        except Exception as e:
            logger.error(f"Failed to refresh service cache: {e}")

    async def _cleanup_expired_services_async(self) -> None:
        """Background task to clean up expired services."""
        while self._running:
            try:
                # Get all service IDs
                service_ids = await self._redis.smembers(self._service_list_key)

                expired_services = []
                for service_id in service_ids:
                    heartbeat_key = f"{self._heartbeat_key_prefix}:{service_id}"
                    heartbeat_time = await self._redis.get(heartbeat_key)

                    if heartbeat_time:
                        last_heartbeat = float(heartbeat_time)
                        if time.time() - last_heartbeat > self.config.service_ttl:
                            expired_services.append(service_id)
                    else:
                        # No heartbeat_async key means service is expired
                        expired_services.append(service_id)

                # Remove expired services
                for service_id in expired_services:
                    await self.deregister_service_async(service_id)
                    logger.info(f"Cleaned up expired service: {service_id}")

                await asyncio.sleep(self.config.service_ttl / 2)  # Clean up every half TTL

            except Exception as e:
                logger.error(f"Error in service cleanup: {e}")
                await asyncio.sleep(30)  # Wait before retrying

    async def get_registry_stats_async(self) -> Dict[str, Any]:
        """Get registry statistics.

        Returns:
            Statistics dictionary
        """
        try:
            await self._refresh_cache_if_needed_async()

            total_services = len(self._service_cache)
            healthy_services = sum(1 for s in self._service_cache.values() if s.healthy)
            service_names = len(set(s.service_name for s in self._service_cache.values()))

            return {
                "total_services": total_services
                "healthy_services": healthy_services
                "unhealthy_services": total_services - healthy_services
                "unique_service_names": service_names
                "cache_last_updated": self._cache_last_updated
                "registry_backend": self.config.registry_backend
            }

        except Exception as e:
            logger.error(f"Failed to get registry stats: {e}")
            return {"error": str(e)}
