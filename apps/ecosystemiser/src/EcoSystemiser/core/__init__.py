from hive_logging import get_logger

logger = get_logger(__name__)

"""
EcoSystemiser Core Components.

Contains the core infrastructure that extends generic Hive packages:
- Database layer (extends hive-db)
- Event bus (extends hive-bus)
- Error handling (extends hive-errors)
- EcoSystemiser-specific event types

This follows the "inherit → extend" pattern:
- Generic packages provide reusable infrastructure
- Core components add EcoSystemiser-specific business logic
"""

from hive_bus import BaseBus, BaseEvent
from hive_db import (
    create_table_if_not_exists,
    get_sqlite_connection,
    sqlite_transaction,
)

# Import base components from hive packages to establish inheritance
from hive_errors import BaseError, BaseErrorReporter, RecoveryStrategy

# Core modules are imported as needed by specific components
# No re-exports at this level to maintain clear module boundaries
