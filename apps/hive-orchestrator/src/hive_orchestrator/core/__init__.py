from hive_logging import get_logger

logger = get_logger(__name__)

"""
Hive Orchestrator Core Components.

Contains the core business logic for Hive orchestration system:
- Database layer (extends hive-db-utils)
- Event bus (extends hive-messaging)
- Error handling (extends hive-error-handling)
- Claude integration (extends generic patterns)

This follows the "inherit → extend" pattern:
- Generic packages provide reusable infrastructure
- Core components add Hive-specific business logic
"""

# Core modules are imported as needed by specific components
# No re-exports at this level to maintain clear module boundaries
