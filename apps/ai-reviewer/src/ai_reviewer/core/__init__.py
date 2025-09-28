"""
AI Reviewer Core Components.

Contains the core infrastructure that extends generic Hive packages:
- Error handling (extends hive-error-handling)
- Event bus (extends hive-messaging)
- Database layer (extends hive-db-utils)
- AI Reviewer-specific service interfaces

This follows the "inherit → extend" pattern:
- Generic packages provide reusable infrastructure
- Core components add AI Reviewer-specific business logic
"""

# Core modules are imported as needed by specific components
# No re-exports at this level to maintain clear module boundaries