"""
EcoSystemiser Core Components.

Contains the core infrastructure that extends generic Hive packages:
- Database layer (extends hive-db-utils)
- Event bus (extends hive-messaging)
- Error handling (extends hive-error-handling)
- EcoSystemiser-specific event types

This follows the "inherit → extend" pattern:
- Generic packages provide reusable infrastructure
- Core components add EcoSystemiser-specific business logic
"""

# Core modules are imported as needed by specific components
# No re-exports at this level to maintain clear module boundaries