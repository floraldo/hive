"""
AI Deployer Core Components.

Contains the core infrastructure that extends generic Hive packages:
- Database layer (extends hive-db via hive-orchestrator)
- Event bus (extends hive-bus)
- Error handling (extends hive-errors)
- Configuration management (extends hive-config)
- AI Deployer-specific service interfaces

This follows the "inherit → extend" pattern:
- Generic packages provide reusable infrastructure
- Core components add AI Deployer-specific business logic
"""

from hive_bus import BaseBus, BaseEvent
from hive_errors import BaseError, BaseErrorReporter, RecoveryStrategy

# Import orchestrator's core services for app-to-app communication
from hive_orchestrator.core.db import (
    get_database_connection,
    get_pooled_connection,
    get_shared_database_service,
)

# Core modules are imported as needed by specific components
# No re-exports at this level to maintain clear module boundaries
