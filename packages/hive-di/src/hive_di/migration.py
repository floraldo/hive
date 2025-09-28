"""
Migration utilities for replacing singleton patterns with dependency injection

This module provides utilities to help migrate from singleton anti-patterns to
proper dependency injection without breaking existing code.
"""

import warnings
from typing import Type, TypeVar, Optional, Dict, Any, Callable
from .container import DIContainer, Lifecycle
from .factories import configure_default_services

T = TypeVar('T')


class GlobalContainerManager:
    """
    Global container manager for backward compatibility during migration

    This provides a global container that can be used as a bridge during migration
    from singleton patterns to proper dependency injection.
    """

    _global_container: Optional[DIContainer] = None

    @classmethod
    def get_global_container(cls) -> DIContainer:
        """Get the global container instance"""
        if cls._global_container is None:
            cls._global_container = DIContainer()
            configure_default_services(cls._global_container)
        return cls._global_container

    @classmethod
    def set_global_container(cls, container: DIContainer) -> None:
        """Set the global container instance"""
        cls._global_container = container

    @classmethod
    def reset_global_container(cls) -> None:
        """Reset the global container (useful for testing)"""
        if cls._global_container:
            cls._global_container.dispose()
        cls._global_container = None


def create_singleton_replacement(service_type: Type[T],
                                deprecated_function_name: str = None) -> Callable[[], T]:
    """
    Create a replacement function for singleton getter functions

    This function creates a replacement that uses the global DI container
    instead of singleton patterns.

    Args:
        service_type: The service interface type to resolve
        deprecated_function_name: Name of the deprecated function for warnings

    Returns:
        Function that resolves the service from the global container
    """
    def resolver() -> T:
        if deprecated_function_name:
            warnings.warn(
                f"{deprecated_function_name} is deprecated. "
                f"Use dependency injection to get {service_type.__name__} instead.",
                DeprecationWarning,
                stacklevel=2
            )

        container = GlobalContainerManager.get_global_container()
        return container.resolve(service_type)

    return resolver


def migrate_configuration_singleton():
    """
    Migration helper for configuration singleton

    This creates a backward-compatible replacement for get_config()
    """
    from .interfaces import IConfigurationService

    return create_singleton_replacement(
        IConfigurationService,
        "get_config"
    )


def migrate_database_connection_pool():
    """
    Migration helper for database connection pool singletons

    This creates backward-compatible replacements for connection pool functions
    """
    from .interfaces import IDatabaseConnectionService

    def get_pooled_connection():
        warnings.warn(
            "get_pooled_connection is deprecated. "
            "Use dependency injection to get IDatabaseConnectionService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        container = GlobalContainerManager.get_global_container()
        db_service = container.resolve(IDatabaseConnectionService)
        return db_service.get_pooled_connection()

    async def get_async_connection():
        warnings.warn(
            "get_async_connection is deprecated. "
            "Use dependency injection to get IDatabaseConnectionService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        container = GlobalContainerManager.get_global_container()
        db_service = container.resolve(IDatabaseConnectionService)
        return await db_service.get_async_connection()

    return get_pooled_connection, get_async_connection


def migrate_error_reporter_singleton():
    """
    Migration helper for error reporter singleton

    This creates a backward-compatible replacement for get_error_reporter()
    """
    from .interfaces import IErrorReportingService

    return create_singleton_replacement(
        IErrorReportingService,
        "get_error_reporter"
    )


def migrate_event_bus_singleton():
    """
    Migration helper for event bus singleton

    This creates a backward-compatible replacement for global event bus access
    """
    from .interfaces import IEventBusService

    return create_singleton_replacement(
        IEventBusService,
        "get_event_bus"
    )


def migrate_claude_service_singleton():
    """
    Migration helper for Claude service singleton

    This creates a backward-compatible replacement for Claude service access
    """
    from .interfaces import IClaudeService

    return create_singleton_replacement(
        IClaudeService,
        "get_claude_service"
    )


def migrate_climate_service_singleton():
    """
    Migration helper for climate service singleton

    This creates backward-compatible replacements for climate service access
    """
    from .interfaces import IClimateService

    return create_singleton_replacement(
        IClimateService,
        "get_enhanced_climate_service"
    )


class MigrationPatch:
    """
    Context manager for patching global functions during migration

    This allows temporary patching of global singleton functions to use
    dependency injection instead.
    """

    def __init__(self, patches: Dict[str, Callable]):
        """
        Initialize migration patch

        Args:
            patches: Dictionary mapping module.function_name to replacement function
        """
        self.patches = patches
        self.original_functions = {}

    def __enter__(self):
        """Apply patches"""
        import importlib

        for module_func_name, replacement in self.patches.items():
            module_name, func_name = module_func_name.rsplit('.', 1)
            module = importlib.import_module(module_name)

            # Store original function
            self.original_functions[module_func_name] = getattr(module, func_name, None)

            # Apply patch
            setattr(module, func_name, replacement)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Remove patches"""
        import importlib

        for module_func_name, original in self.original_functions.items():
            module_name, func_name = module_func_name.rsplit('.', 1)
            module = importlib.import_module(module_name)

            if original is not None:
                setattr(module, func_name, original)
            else:
                delattr(module, func_name)


def create_migration_patches() -> Dict[str, Callable]:
    """
    Create migration patches for all singleton functions

    Returns:
        Dictionary of patches to apply
    """
    patches = {}

    # Configuration
    patches['hive_config.unified_config.get_config'] = migrate_configuration_singleton()

    # Database connections
    get_pooled_conn, get_async_conn = migrate_database_connection_pool()
    patches['hive_core_db.connection_pool.get_pooled_connection'] = get_pooled_conn
    patches['hive_core_db.async_connection_pool.get_async_connection'] = get_async_conn

    # Error reporting
    patches['hive_orchestrator.core.errors.error_reporter.get_error_reporter'] = migrate_error_reporter_singleton()

    # Climate service
    patches['EcoSystemiser.profile_loader.climate.service.get_enhanced_climate_service'] = migrate_climate_service_singleton()

    return patches


def apply_global_migration_patches():
    """
    Apply all migration patches globally

    This is a convenience function that applies all singleton replacement patches.
    Use this during migration period to maintain backward compatibility.
    """
    patches = create_migration_patches()

    # Apply patches permanently (until process restart)
    for module_func_name, replacement in patches.items():
        try:
            import importlib
            module_name, func_name = module_func_name.rsplit('.', 1)
            module = importlib.import_module(module_name)
            setattr(module, func_name, replacement)
        except (ImportError, AttributeError):
            # Module or function doesn't exist, skip
            pass


def create_test_container(overrides: Optional[Dict[Type, Any]] = None) -> DIContainer:
    """
    Create a test container with mock services

    Args:
        overrides: Optional dictionary of service type -> mock instance

    Returns:
        Configured test container
    """
    from unittest.mock import Mock
    from .interfaces import (
        IConfigurationService,
        IDatabaseConnectionService,
        IEventBusService,
        IErrorReportingService,
        IClaudeService,
        IClimateService,
        IJobManagerService
    )

    container = DIContainer()

    # Create mock services
    mock_config = Mock(spec=IConfigurationService)
    mock_db = Mock(spec=IDatabaseConnectionService)
    mock_events = Mock(spec=IEventBusService)
    mock_errors = Mock(spec=IErrorReportingService)
    mock_claude = Mock(spec=IClaudeService)
    mock_climate = Mock(spec=IClimateService)
    mock_jobs = Mock(spec=IJobManagerService)

    # Apply overrides
    if overrides:
        for service_type, mock_instance in overrides.items():
            if service_type == IConfigurationService:
                mock_config = mock_instance
            elif service_type == IDatabaseConnectionService:
                mock_db = mock_instance
            elif service_type == IEventBusService:
                mock_events = mock_instance
            elif service_type == IErrorReportingService:
                mock_errors = mock_instance
            elif service_type == IClaudeService:
                mock_claude = mock_instance
            elif service_type == IClimateService:
                mock_climate = mock_instance
            elif service_type == IJobManagerService:
                mock_jobs = mock_instance

    # Register mock services
    container.register_instance(IConfigurationService, mock_config)
    container.register_instance(IDatabaseConnectionService, mock_db)
    container.register_instance(IEventBusService, mock_events)
    container.register_instance(IErrorReportingService, mock_errors)
    container.register_instance(IClaudeService, mock_claude)
    container.register_instance(IClimateService, mock_climate)
    container.register_instance(IJobManagerService, mock_jobs)

    return container


# Example usage and migration patterns
def example_migration_usage():
    """
    Example of how to use the migration utilities

    This shows various patterns for migrating from singletons to DI.
    """

    # Pattern 1: Replace global singleton function during migration
    with MigrationPatch({
        'mymodule.get_config': migrate_configuration_singleton()
    }):
        # Code using old singleton pattern will now use DI
        from mymodule import get_config
        config = get_config()  # This now uses DI under the hood

    # Pattern 2: Global application of migration patches
    apply_global_migration_patches()

    # Pattern 3: Testing with DI
    test_container = create_test_container()
    GlobalContainerManager.set_global_container(test_container)

    # Pattern 4: Production application setup
    container = DIContainer()
    configure_default_services(container)
    GlobalContainerManager.set_global_container(container)

    # Pattern 5: Service-specific configuration
    from .interfaces import IConfigurationService
    from .services import ConfigurationService

    container.register(
        IConfigurationService,
        lambda: ConfigurationService(config_source={'database': {'max_connections': 20}}),
        Lifecycle.SINGLETON
    )