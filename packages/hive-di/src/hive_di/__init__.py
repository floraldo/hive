"""
Hive Dependency Injection Framework

A lightweight dependency injection container for the Hive platform that eliminates
singleton anti-patterns and enables proper inversion of control.

Key Features:
- Service registration with multiple lifecycle options
- Automatic dependency resolution with circular dependency detection
- Factory pattern support for complex object creation
- Scoped instances (singleton, transient, scoped)
- Thread-safe operation
- Easy mocking and testing support
"""

from .container import DIContainer, Lifecycle
from .interfaces import (
    IConfigurationService,
    IDatabaseConnectionService,
    IEventBusService,
    IErrorReportingService,
    IClaudeService
)
from .factories import (
    ConfigurationServiceFactory,
    DatabaseServiceFactory,
    EventBusServiceFactory,
    ErrorReporterServiceFactory,
    ClaudeServiceFactory
)
from .exceptions import (
    DIException,
    ServiceNotRegisteredException,
    CircularDependencyException,
    ServiceRegistrationException
)

__all__ = [
    'DIContainer',
    'Lifecycle',
    'IConfigurationService',
    'IDatabaseConnectionService',
    'IEventBusService',
    'IErrorReportingService',
    'IClaudeService',
    'ConfigurationServiceFactory',
    'DatabaseServiceFactory',
    'EventBusServiceFactory',
    'ErrorReporterServiceFactory',
    'ClaudeServiceFactory',
    'DIException',
    'ServiceNotRegisteredException',
    'CircularDependencyException',
    'ServiceRegistrationException'
]

__version__ = "1.0.0"