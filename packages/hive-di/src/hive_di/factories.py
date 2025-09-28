"""
Service Factories for Dependency Injection

Factory classes that create configured instances of core Hive services.
These factories handle the complexity of service construction while enabling
proper dependency injection and configuration management.
"""

from typing import Dict, Any, Optional, List, Type
from .interfaces import (
    IServiceFactory,
    IConfigurationService,
    IDatabaseConnectionService,
    IEventBusService,
    IErrorReportingService,
    IClaudeService,
    IClimateService,
    IJobManagerService
)


class ConfigurationServiceFactory(IServiceFactory):
    """Factory for creating configuration service instances"""

    def create(self, config: Optional[Dict[str, Any]] = None) -> IConfigurationService:
        """Create a configuration service instance"""
        from .services.configuration_service import ConfigurationService

        config_source = config.get('source') if config else None
        config_path = config.get('path') if config else None
        use_environment = config.get('use_environment', True) if config else True

        return ConfigurationService(
            config_source=config_source,
            config_path=config_path,
            use_environment=use_environment
        )

    def get_dependencies(self) -> List[Type]:
        """Configuration service has no dependencies"""
        return []


class DatabaseServiceFactory(IServiceFactory):
    """Factory for creating database connection service instances"""

    def create(self, config: Optional[Dict[str, Any]] = None) -> IDatabaseConnectionService:
        """Create a database connection service instance"""
        from .services.database_service import DatabaseConnectionService

        # If no config provided, the service will get it from the injected configuration service
        return DatabaseConnectionService(config=config)

    def get_dependencies(self) -> List[Type]:
        """Database service depends on configuration"""
        return [IConfigurationService]


class EventBusServiceFactory(IServiceFactory):
    """Factory for creating event bus service instances"""

    def create(self, config: Optional[Dict[str, Any]] = None) -> IEventBusService:
        """Create an event bus service instance"""
        from .services.event_bus_service import EventBusService

        return EventBusService(config=config)

    def get_dependencies(self) -> List[Type]:
        """Event bus depends on configuration and database services"""
        return [IConfigurationService, IDatabaseConnectionService]


class ErrorReporterServiceFactory(IServiceFactory):
    """Factory for creating error reporter service instances"""

    def create(self, config: Optional[Dict[str, Any]] = None) -> IErrorReportingService:
        """Create an error reporter service instance"""
        from .services.error_reporting_service import ErrorReportingService

        return ErrorReportingService(config=config)

    def get_dependencies(self) -> List[Type]:
        """Error reporter depends on configuration, database, and event bus"""
        return [IConfigurationService, IDatabaseConnectionService, IEventBusService]


class ClaudeServiceFactory(IServiceFactory):
    """Factory for creating Claude service instances"""

    def create(self, config: Optional[Dict[str, Any]] = None) -> IClaudeService:
        """Create a Claude service instance"""
        from .services.claude_service import ClaudeService

        return ClaudeService(config=config)

    def get_dependencies(self) -> List[Type]:
        """Claude service depends on configuration and error reporting"""
        return [IConfigurationService, IErrorReportingService]


class ClimateServiceFactory(IServiceFactory):
    """Factory for creating climate service instances"""

    def create(self, config: Optional[Dict[str, Any]] = None) -> IClimateService:
        """Create a climate service instance"""
        from .services.climate_service import ClimateService

        return ClimateService(config=config)

    def get_dependencies(self) -> List[Type]:
        """Climate service depends on configuration and database"""
        return [IConfigurationService, IDatabaseConnectionService]


class JobManagerServiceFactory(IServiceFactory):
    """Factory for creating job manager service instances"""

    def create(self, config: Optional[Dict[str, Any]] = None) -> IJobManagerService:
        """Create a job manager service instance"""
        from .services.job_manager_service import JobManagerService

        return JobManagerService(config=config)

    def get_dependencies(self) -> List[Type]:
        """Job manager depends on configuration, database, and event bus"""
        return [IConfigurationService, IDatabaseConnectionService, IEventBusService]


# Helper function to create factory instances
def create_factory(factory_type: str, **kwargs) -> IServiceFactory:
    """
    Create a factory instance by type name

    Args:
        factory_type: Name of the factory type
        **kwargs: Additional arguments for factory creation

    Returns:
        Factory instance

    Raises:
        ValueError: If factory type is not recognized
    """
    factories = {
        'configuration': ConfigurationServiceFactory,
        'database': DatabaseServiceFactory,
        'event_bus': EventBusServiceFactory,
        'error_reporter': ErrorReporterServiceFactory,
        'claude': ClaudeServiceFactory,
        'climate': ClimateServiceFactory,
        'job_manager': JobManagerServiceFactory
    }

    if factory_type not in factories:
        available = ', '.join(factories.keys())
        raise ValueError(f"Unknown factory type '{factory_type}'. Available: {available}")

    return factories[factory_type](**kwargs)


# Configuration helpers
def get_default_service_registrations() -> Dict[Type, Dict[str, Any]]:
    """Get default service registrations for the Hive platform"""
    return {
        IConfigurationService: {
            'factory': ConfigurationServiceFactory(),
            'lifecycle': 'singleton'
        },
        IDatabaseConnectionService: {
            'factory': DatabaseServiceFactory(),
            'lifecycle': 'singleton'
        },
        IEventBusService: {
            'factory': EventBusServiceFactory(),
            'lifecycle': 'singleton'
        },
        IErrorReportingService: {
            'factory': ErrorReporterServiceFactory(),
            'lifecycle': 'singleton'
        },
        IClaudeService: {
            'factory': ClaudeServiceFactory(),
            'lifecycle': 'singleton'
        },
        IClimateService: {
            'factory': ClimateServiceFactory(),
            'lifecycle': 'singleton'
        },
        IJobManagerService: {
            'factory': JobManagerServiceFactory(),
            'lifecycle': 'singleton'
        }
    }


def configure_default_services(container) -> None:
    """
    Configure the default Hive services in a DI container

    Args:
        container: DIContainer instance to configure
    """
    from .container import Lifecycle

    registrations = get_default_service_registrations()

    for service_type, config in registrations.items():
        lifecycle = getattr(Lifecycle, config['lifecycle'].upper())
        container.register(
            service_type=service_type,
            factory=config['factory'].create,
            lifecycle=lifecycle
        )