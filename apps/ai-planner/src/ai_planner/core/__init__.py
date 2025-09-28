"""
AI Planner Core Components.

Contains the core infrastructure that extends generic Hive packages:
- Error handling (extends hive-error-handling)
- Event bus (extends hive-messaging)
- Database layer (extends hive-db-utils via hive-orchestrator)
- AI Planner-specific service interfaces

This follows the "inherit → extend" pattern:
- Generic packages provide reusable infrastructure
- Core components add AI Planner-specific business logic
"""

# Core modules are imported as needed by specific components
# No re-exports at this level to maintain clear module boundaries