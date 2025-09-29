from hive_logging import get_logger

logger = get_logger(__name__)

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


# Import orchestrator's core services for app-to-app communication

# Core modules are imported as needed by specific components
# No re-exports at this level to maintain clear module boundaries
