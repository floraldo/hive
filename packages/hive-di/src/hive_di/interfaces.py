"""
Service Interfaces for Dependency Injection

Abstract base classes that define the contracts for major services in the Hive platform.
These interfaces enable proper dependency injection and testing by allowing easy mocking
and implementation swapping.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, AsyncContextManager, List, Callable
from contextlib import asynccontextmanager
from datetime import datetime


class IConfigurationService(ABC):
    """Interface for configuration management services"""

    @abstractmethod
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        pass

    @abstractmethod
    def get_claude_config(self) -> Dict[str, Any]:
        """Get Claude service configuration"""
        pass

    @abstractmethod
    def get_event_bus_config(self) -> Dict[str, Any]:
        """Get event bus configuration"""
        pass

    @abstractmethod
    def get_error_reporting_config(self) -> Dict[str, Any]:
        """Get error reporting configuration"""
        pass

    @abstractmethod
    def get_climate_config(self) -> Dict[str, Any]:
        """Get climate service configuration"""
        pass

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        pass

    @abstractmethod
    def reload(self) -> None:
        """Reload configuration from source"""
        pass


class IDatabaseConnectionService(ABC):
    """Interface for database connection management"""

    @abstractmethod
    def get_connection(self):
        """Get a database connection (sync)"""
        pass

    @abstractmethod
    async def get_async_connection(self):
        """Get an async database connection"""
        pass

    @abstractmethod
    def get_pooled_connection(self):
        """Get a pooled connection context manager"""
        pass

    @abstractmethod
    async def get_async_pooled_connection(self):
        """Get an async pooled connection context manager"""
        pass

    @abstractmethod
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        pass

    @abstractmethod
    def close_all_connections(self) -> None:
        """Close all connections and clean up"""
        pass


class IEventBusService(ABC):
    """Interface for event bus operations"""

    @abstractmethod
    def publish(self, event_type: str, payload: Dict[str, Any],
                source_agent: str, correlation_id: Optional[str] = None) -> str:
        """Publish an event to the bus"""
        pass

    @abstractmethod
    async def publish_async(self, event_type: str, payload: Dict[str, Any],
                           source_agent: str, correlation_id: Optional[str] = None) -> str:
        """Publish an event asynchronously"""
        pass

    @abstractmethod
    def subscribe(self, event_pattern: str, callback: Callable, subscriber_agent: str) -> str:
        """Subscribe to events matching a pattern"""
        pass

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events"""
        pass

    @abstractmethod
    def get_events(self, event_type: Optional[str] = None,
                   since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get events from the bus"""
        pass

    @abstractmethod
    def replay_events(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Replay events for a correlation ID"""
        pass


class IErrorReportingService(ABC):
    """Interface for error reporting and management"""

    @abstractmethod
    def report_error(self, error: Exception, context: Optional[Dict[str, Any]] = None,
                    severity: str = "error", component: Optional[str] = None) -> str:
        """Report an error and return error ID"""
        pass

    @abstractmethod
    async def report_error_async(self, error: Exception, context: Optional[Dict[str, Any]] = None,
                                severity: str = "error", component: Optional[str] = None) -> str:
        """Report an error asynchronously"""
        pass

    @abstractmethod
    def get_error_summary(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get error summary statistics"""
        pass

    @abstractmethod
    def get_error_details(self, error_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific error"""
        pass

    @abstractmethod
    def mark_error_resolved(self, error_id: str, resolution_note: Optional[str] = None) -> bool:
        """Mark an error as resolved"""
        pass


class IClaudeService(ABC):
    """Interface for Claude AI service operations"""

    @abstractmethod
    def send_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a message to Claude service"""
        pass

    @abstractmethod
    async def send_message_async(self, message: str,
                                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a message to Claude service asynchronously"""
        pass

    @abstractmethod
    def get_service_status(self) -> Dict[str, Any]:
        """Get Claude service status"""
        pass

    @abstractmethod
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get rate limiting status"""
        pass

    @abstractmethod
    def reset_rate_limits(self) -> None:
        """Reset rate limiting counters"""
        pass


class IClimateService(ABC):
    """Interface for climate data services"""

    @abstractmethod
    def get_weather_data(self, location: Dict[str, Any],
                        date_range: Dict[str, Any]) -> Dict[str, Any]:
        """Get weather data for location and date range"""
        pass

    @abstractmethod
    async def get_weather_data_async(self, location: Dict[str, Any],
                                    date_range: Dict[str, Any]) -> Dict[str, Any]:
        """Get weather data asynchronously"""
        pass

    @abstractmethod
    def get_available_adapters(self) -> List[str]:
        """Get list of available climate data adapters"""
        pass

    @abstractmethod
    def get_adapter_capabilities(self, adapter_name: str) -> Dict[str, Any]:
        """Get capabilities for a specific adapter"""
        pass


class IJobManagerService(ABC):
    """Interface for job management services"""

    @abstractmethod
    def submit_job(self, job_config: Dict[str, Any]) -> str:
        """Submit a job and return job ID"""
        pass

    @abstractmethod
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a specific job"""
        pass

    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        pass

    @abstractmethod
    def get_job_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get results from a completed job"""
        pass


# Factory interfaces for creating services
class IServiceFactory(ABC):
    """Base interface for service factories"""

    @abstractmethod
    def create(self, config: Optional[Dict[str, Any]] = None) -> Any:
        """Create a service instance"""
        pass

    @abstractmethod
    def get_dependencies(self) -> List[type]:
        """Get list of required dependency types"""
        pass


class IDisposable(ABC):
    """Interface for services that need cleanup"""

    @abstractmethod
    def dispose(self) -> None:
        """Clean up resources"""
        pass